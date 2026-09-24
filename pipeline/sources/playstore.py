from datetime import datetime
import uuid
import logging

from google_play_scraper import Sort, reviews

from pipeline.sources.base import SourceBase, hash_author
from shared.models import RawRecord
from shared.enums import Source, ItemType, Product

logger = logging.getLogger(__name__)

class PlayStoreSource(SourceBase):
    def __init__(self):
        self.errors = []

    def fetch(self, since: datetime, cap: int) -> list[RawRecord]:
        logger.info(f"Fetching Play Store records since {since}, cap {cap}")
        app_id = "com.google.android.apps.photos"
        locales = ["en-in", "en-us", "hi-in"]
        
        all_records = []
        
        # Divide cap among locales roughly
        cap_per_locale = max(1, cap // len(locales))
        
        for locale in locales:
            lang, country = locale.split("-")
            
            # Fetch reviews
            try:
                result, _ = reviews(
                    app_id,
                    lang=lang,
                    country=country,
                    sort=Sort.NEWEST,
                    count=cap_per_locale
                )
                
                for r in result:
                    dt = r.get("at")
                    if not dt:
                        continue
                    
                    # Convert naive datetime to timezone-aware UTC
                    if dt.tzinfo is None:
                        from datetime import timezone
                        dt = dt.replace(tzinfo=timezone.utc)
                    
                    if dt < since:
                        # Since it's sorted NEWEST, we can stop for this locale
                        break
                    
                    text = r.get("content", "").strip()
                    if not text:
                        continue
                    
                    author = r.get("userName")
                    review_id = r.get("reviewId")
                    stars = r.get("score")
                    
                    record_id = f"ps_{review_id}" if review_id else f"ps_{uuid.uuid4().hex[:12]}"
                    
                    all_records.append(RawRecord(
                        record_id=record_id,
                        source=Source.PLAYSTORE,
                        item_type=ItemType.REVIEW,
                        product=Product.GOOGLE_PHOTOS,
                        author_hash=hash_author(author),
                        created_at=dt,
                        text=text,
                        extra={"stars": stars, "locale": locale}
                    ))
            except Exception as e:
                logger.error(f"Error fetching Play Store reviews for {locale}: {e}")
                self.errors.append(f"Error fetching Play Store reviews for {locale}: {e}")
                
        # Sort combined results by date descending and truncate to cap just in case
        all_records.sort(key=lambda x: x.created_at, reverse=True)
        return all_records[:cap]
