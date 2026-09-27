from datetime import datetime
import uuid
import logging
import concurrent.futures
import yaml
from pathlib import Path
from apify_client import ApifyClient
from pipeline.sources.base import SourceBase, hash_author
from shared.models import RawRecord
from shared.enums import Source, ItemType, Product
from pipeline.db import execute_sql

logger = logging.getLogger(__name__)

def estimate_cost_and_scale(name: str, max_items: int, budget: float, cost_per_item: float = 0.005) -> int:
    estimated_cost = max_items * cost_per_item
    logger.info(f"[{name}] Estimated count: {max_items}, cost: ${estimated_cost:.2f}")
    if estimated_cost > budget:
        scaled_max = int(budget / cost_per_item)
        logger.info(f"[{name}] Scaling down cap to {scaled_max} to fit budget ${budget}")
        return scaled_max
    return max_items

class RedditSource(SourceBase):
    def __init__(self, token: str):
        self.client = ApifyClient(token)
        self.errors = []
        self.remaining_budget = 4.0
        
    def _run_apify(self, run_input, term_str, community, since):
        local_records = []
        try:
            run = self.client.actor("harshmaur/reddit-scraper").call(run_input=run_input)
            dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "defaultDatasetId", None) or getattr(run, "default_dataset_id", None)
            
            for item in self.client.dataset(dataset_id).iterate_items():
                dt_str = item.get("createdAt") or item.get("commentCreatedAt")
                if dt_str:
                    try:
                        if dt_str.endswith('Z'):
                            dt_str = dt_str.replace("Z", "+00:00")
                        dt = datetime.fromisoformat(dt_str)
                        if dt.tzinfo is None:
                            from datetime import timezone
                            dt = dt.replace(tzinfo=timezone.utc)
                            
                        if dt < since:
                            continue
                    except ValueError:
                        continue
                else:
                    continue
                
                data_type = item.get("dataType")
                product = Product.GOOGLE_PHOTOS
                if community in ['r/iphone', 'r/applehelp', 'r/ios']:
                    product = Product.APPLE_PHOTOS
                elif community in ['r/samsung', 'r/GalaxyS24']:
                    product = Product.SAMSUNG_GALLERY
                
                if data_type == "post":
                    item_type = ItemType.POST
                    text = f"{item.get('title', '')}\n{item.get('body', '')}".strip()
                    url = item.get("postUrl")
                    author = item.get("authorName")
                    parsed_id = item.get("parsedId")
                    subreddit = item.get("parsedCommunityName")
                elif data_type == "comment":
                    item_type = ItemType.COMMENT
                    text = item.get("body", "")
                    url = item.get("url")
                    author = item.get("authorName")
                    parsed_id = item.get("id")
                    subreddit = item.get("subredditName")
                else:
                    continue
                
                if not text:
                    continue
                
                record_id = f"rd_{parsed_id}" if parsed_id else f"rd_{uuid.uuid4().hex[:12]}"
                
                local_records.append(RawRecord(
                    record_id=record_id,
                    source=Source.REDDIT,
                    item_type=item_type,
                    product=product,
                    url=url,
                    author_hash=hash_author(author),
                    created_at=dt,
                    text=text,
                    extra={"subreddit": subreddit, "search_term": term_str, "community_search": community}
                ))
        except Exception as e:
            err_msg = f"Error fetching Reddit for '{term_str}' in '{community}': {e}"
            logger.error(err_msg)
            return local_records, err_msg
        return local_records, None

    def fetch(self, since: datetime, cap: int) -> list[RawRecord]:
        logger.info(f"Fetching Reddit records since {since}, cap {cap}")
        config_path = Path(__file__).resolve().parent.parent.parent / "reddit_search_config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
            
        records = []
        
        # 1. Comment mining
        rows = execute_sql(
            "SELECT url FROM raw_records WHERE source = 'reddit' AND item_type = 'post' "
            "AND relevance_class IN ('specific_episode', 'success_or_tip', 'believes_lost', 'general_search_complaint')"
        )
        start_urls = [{"url": r['url']} for r in rows if r['url']]
        
        if start_urls:
            max_comments = len(start_urls) * 15
            scaled_max = estimate_cost_and_scale("Comment Mining", max_comments, self.remaining_budget)
            if scaled_max > 0:
                run_input = {
                    "startUrls": start_urls,
                    "crawlCommentsPerPost": True,
                    "maxCommentsPerPost": 15,
                    "searchComments": False,
                    "searchPosts": False
                }
                actual_run_max = scaled_max
                # Cap the start urls if we can't afford all
                if scaled_max < max_comments:
                    allowed_urls = max(1, scaled_max // 15)
                    run_input["startUrls"] = start_urls[:allowed_urls]
                
                res, err = self._run_apify(run_input, "comment_mining", "", since)
                if err: self.errors.append(err)
                records.extend(res)
                self.remaining_budget -= len(res) * 0.005
                logger.info(f"Fetched {len(res)} comments. Remaining budget: ${self.remaining_budget:.2f}")

        # 2. Scaled winners & Other apps
        reddit_wide = config.get("reddit_wide_terms", {})
        community_searches = config.get("community_searches", {})
        tournament = config.get("tournament", {})
        
        searches = []
        for term, limit in reddit_wide.items():
            searches.append((term, "", limit))
        for community, terms_dict in community_searches.items():
            for term, limit in terms_dict.items():
                searches.append((term, community, limit))
                
        for term, community, limit in searches:
            if self.remaining_budget <= 0.01:
                logger.warning("Apify budget exhausted.")
                break
                
            max_items = limit + (limit * 3) # maxCommentsCount: 3 means up to 3 comments per post
            scaled_max = estimate_cost_and_scale(f"Search: {term} in {community}", max_items, self.remaining_budget)
            
            if scaled_max > 0:
                post_limit = scaled_max // 4 # Approximate split between posts and comments
                if post_limit < 1: post_limit = 1
                
                run_input = {
                    "searchTerms": [term],
                    "withinCommunity": community,
                    "searchPosts": tournament.get("searchPosts", True),
                    "searchComments": tournament.get("searchComments", True),
                    "searchSort": tournament.get("searchSort", "relevance"),
                    "postedAfter": since.strftime("%Y-%m-%d"),
                    "maxPostsCount": post_limit,
                    "maxCommentsCount": tournament.get("maxCommentsCount", 3)
                }
                res, err = self._run_apify(run_input, term, community, since)
                if err: self.errors.append(err)
                records.extend(res)
                self.remaining_budget -= len(res) * 0.005
                
        records.sort(key=lambda x: x.created_at, reverse=True)
        return records[:cap]
