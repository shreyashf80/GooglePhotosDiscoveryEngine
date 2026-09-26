from datetime import datetime
import uuid
import logging

from apify_client import ApifyClient

from pipeline.sources.base import SourceBase, hash_author
from shared.models import RawRecord
from shared.enums import Source, ItemType, Product

logger = logging.getLogger(__name__)

class RedditSource(SourceBase):
    def __init__(self, token: str):
        self.client = ApifyClient(token)
        self.errors = []
    
    def fetch(self, since: datetime, cap: int) -> list[RawRecord]:
        logger.info(f"Fetching Reddit records since {since}, cap {cap}")
        import yaml
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent.parent / "reddit_search_config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
            
        reddit_wide_terms = config.get("reddit_wide_terms", [])
        community_searches = config.get("community_searches", {})
        tournament = config.get("tournament", {})
        
        searches = []
        for term in reddit_wide_terms:
            searches.append((term, ""))
        for community, terms in community_searches.items():
            for term in terms:
                searches.append((term, community))
                
        records = []
        
        # Use ThreadPoolExecutor to run Apify searches in parallel to save time
        import concurrent.futures
        
        def fetch_for_search(term, community):
            max_posts = 30 if community else 20
            run_input = {
                "searchTerms": [term],
                "withinCommunity": community,
                "searchPosts": tournament.get("searchPosts", True),
                "searchComments": tournament.get("searchComments", False),
                "searchSort": tournament.get("searchSort", "relevance"),
                "postedAfter": since.strftime("%Y-%m-%d"),
                "maxPostsCount": max_posts,
                "maxCommentsCount": 0 if not tournament.get("searchComments", False) else tournament.get("maxCommentsCount", 3)
            }
            
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
                        product=Product.GOOGLE_PHOTOS,
                        url=url,
                        author_hash=hash_author(author),
                        created_at=dt,
                        text=text,
                        extra={"subreddit": subreddit, "search_term": term, "community_search": community}
                    ))
            except Exception as e:
                err_msg = f"Error fetching Reddit for term '{term}' in '{community}': {e}"
                logger.error(err_msg)
                return local_records, err_msg
            return local_records, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_search = {executor.submit(fetch_for_search, t, c): (t, c) for t, c in searches}
            for future in concurrent.futures.as_completed(future_to_search):
                t, c = future_to_search[future]
                try:
                    res, err = future.result()
                    if err:
                        self.errors.append(err)
                    records.extend(res)
                except Exception as exc:
                    self.errors.append(f"Search {t} in {c} generated an exception: {exc}")
                
                if len(records) >= cap:
                    break
        
        records.sort(key=lambda x: x.created_at, reverse=True)
        return records[:cap]
