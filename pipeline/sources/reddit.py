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
        search_terms = [
            "google photos can't find photo",
            "google photos search not finding",
            "find old photo google photos",
            "ask photos",
            "google photos search kaam nahi kar raha",
            "google photos purani photo kaise dhunde",
            "google photos not searching correctly"
        ]
        
        communities = ["r/googlephotos", ""]
        records = []
        
        for community in communities:
            if len(records) >= cap:
                break
                
            run_input = {
                "searchTerms": search_terms,
                "withinCommunity": community,
                "searchPosts": True,
                "searchComments": True,
                "searchSort": "new",
                "postedAfter": since.strftime("%Y-%m-%d"),
                "maxPostsCount": max(1, cap // 2),
                "maxCommentsCount": max(1, cap // 2)
            }
            
            try:
                run = self.client.actor("harshmaur/reddit-scraper").call(run_input=run_input)
                dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "defaultDatasetId", None) or getattr(run, "default_dataset_id", None)
                
                for item in self.client.dataset(dataset_id).iterate_items():
                    dt_str = item.get("createdAt") or item.get("commentCreatedAt")
                    if dt_str:
                        try:
                            # Append UTC timezone if not present, and handle 'Z'
                            if dt_str.endswith('Z'):
                                dt_str = dt_str.replace("Z", "+00:00")
                            dt = datetime.fromisoformat(dt_str)
                            if dt.tzinfo is None:
                                # Assume UTC if naive
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
                    
                    records.append(RawRecord(
                        record_id=record_id,
                        source=Source.REDDIT,
                        item_type=item_type,
                        product=Product.GOOGLE_PHOTOS,
                        url=url,
                        author_hash=hash_author(author),
                        created_at=dt,
                        text=text,
                        extra={"subreddit": subreddit}
                    ))
                    
                    if len(records) >= cap:
                        break
                    
            except Exception as e:
                logger.error(f"Error fetching Reddit for community '{community}': {e}")
                self.errors.append(f"Error fetching Reddit for community '{community}': {e}")
                
        records.sort(key=lambda x: x.created_at, reverse=True)
        return records[:cap]
