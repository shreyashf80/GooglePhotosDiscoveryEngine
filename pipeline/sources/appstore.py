import logging
import uuid
import requests
from datetime import datetime

from pipeline.sources.base import SourceBase, hash_author
from pipeline.config import APPSTORE_PRODUCT_ID
from shared.models import RawRecord
from shared.enums import Source, ItemType, Product

logger = logging.getLogger(__name__)

class AppStoreSource(SourceBase):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.errors = []
        
    def fetch(self, since: datetime, cap: int) -> list[RawRecord]:
        logger.info(f"Fetching App Store records since {since}, cap {cap}")
        app_id = APPSTORE_PRODUCT_ID
        countries = ["us", "in"]
        
        all_records = []
        cap_per_country = max(1, cap // len(countries))
        
        for country in countries:
            page = 1
            fetched_for_country = 0
            
            while fetched_for_country < cap_per_country:
                params = {
                    "engine": "apple_reviews",
                    "product_id": app_id,
                    "country": country,
                    "sort": "mostrecent",
                    "page": page,
                    "api_key": self.api_key
                }
                
                try:
                    resp = requests.get("https://serpapi.com/search.json", params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    reviews = data.get("reviews", [])
                    if not reviews:
                        break
                        
                    stop_pagination = False
                    for r in reviews:
                        dt_str = r.get("review_date") or r.get("date")
                        # Serpapi apple_reviews actually returns date like 'Oct 29, 2023' or '2023-10-29' 
                        # We must parse defensively.
                        if not dt_str:
                            continue
                        
                        try:
                            # Try ISO format
                            if dt_str.endswith("Z"):
                                dt_str = dt_str.replace("Z", "+00:00")
                            dt = datetime.fromisoformat(dt_str)
                            if dt.tzinfo is None:
                                from datetime import timezone
                                dt = dt.replace(tzinfo=timezone.utc)
                        except ValueError:
                            # Try common format: Oct 29, 2023
                            try:
                                dt = datetime.strptime(dt_str, "%b %d, %Y")
                                from datetime import timezone
                                dt = dt.replace(tzinfo=timezone.utc)
                            except ValueError:
                                # Skip if date unparseable
                                continue
                                
                        if dt < since:
                            stop_pagination = True
                            break # sorted mostrecent
                            
                        text = f"{r.get('title', '')}\n{r.get('text', '')}".strip()
                        if not text:
                            continue
                            
                        author = r.get("author", {}).get("name") if isinstance(r.get("author"), dict) else r.get("author")
                        review_id = r.get("id")
                        stars = r.get("rating")
                        
                        record_id = f"as_{review_id}" if review_id else f"as_{uuid.uuid4().hex[:12]}"
                        
                        all_records.append(RawRecord(
                            record_id=record_id,
                            source=Source.APPSTORE,
                            item_type=ItemType.REVIEW,
                            product=Product.GOOGLE_PHOTOS,
                            author_hash=hash_author(author),
                            created_at=dt,
                            text=text,
                            extra={"stars": stars, "country": country}
                        ))
                        fetched_for_country += 1
                        if fetched_for_country >= cap_per_country:
                            stop_pagination = True
                            break
                            
                    if stop_pagination or page > 50:
                        break
                        
                    page += 1
                except Exception as e:
                    logger.error(f"Error fetching App Store reviews for {country} page {page}: {e}")
                    self.errors.append(f"Error fetching App Store reviews for {country} page {page}: {e}")
                    break
                    
        all_records.sort(key=lambda x: x.created_at, reverse=True)
        return all_records[:cap]
