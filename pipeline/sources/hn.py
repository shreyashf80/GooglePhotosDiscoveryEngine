import requests
from datetime import datetime, timezone
import uuid
import logging
from pipeline.sources.base import SourceBase, hash_author
from shared.models import RawRecord
from shared.enums import Source, ItemType, Product

logger = logging.getLogger(__name__)

class HackerNewsSource(SourceBase):
    def __init__(self):
        self.errors = []
        
    def fetch(self, since: datetime, cap: int = 300) -> list[RawRecord]:
        logger.info(f"Fetching HN records since {since}, cap {cap}")
        
        queries = ["\"google photos\" search", "\"apple photos\" search", "\"can't find\" photo"]
        since_ts = int(since.timestamp())
        records = []
        
        for query in queries:
            if len(records) >= cap:
                break
            
            try:
                url = "https://hn.algolia.com/api/v1/search_by_date"
                params = {
                    "query": query,
                    "numericFilters": f"created_at_i>{since_ts}",
                    "hitsPerPage": 100
                }
                logger.info(f"Querying Algolia API for '{query}'...")
                resp = requests.get(url, params=params, timeout=5)
                resp.raise_for_status()
                hits = resp.json().get("hits", [])
                logger.info(f"Got {len(hits)} hits for '{query}'")
                
                for hit in hits:
                    dt = datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc)
                    text = hit.get("comment_text") or hit.get("story_text") or hit.get("title") or ""
                    
                    # Remove HTML tags minimally
                    import re
                    text = re.sub('<[^<]+?>', '', text)
                    
                    if not text.strip():
                        continue
                        
                    item_type = ItemType.COMMENT if hit.get("comment_text") else ItemType.POST
                    author = hit.get("author", "unknown")
                    url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
                    
                    records.append(RawRecord(
                        record_id=f"hn_{hit['objectID']}",
                        source=Source.COMMUNITY,
                        item_type=item_type,
                        product=Product.GOOGLE_PHOTOS if "apple" not in query else Product.APPLE_PHOTOS,
                        url=url,
                        author_hash=hash_author(author),
                        created_at=dt,
                        text=text.strip(),
                        extra={"search_term": query, "hn_id": hit['objectID']}
                    ))
            except Exception as e:
                err_msg = f"HN search error for '{query}': {e}"
                logger.error(err_msg)
                self.errors.append(err_msg)
                
        records.sort(key=lambda x: x.created_at, reverse=True)
        return records[:cap]
