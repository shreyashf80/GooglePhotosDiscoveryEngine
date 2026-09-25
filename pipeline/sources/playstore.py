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
            
            # Fetch reviews in chunks using continuation token
            try:
                continuation_token = None
                fetched_for_locale = 0
                
                while fetched_for_locale < cap_per_locale:
                    result, continuation_token = reviews(
                        app_id,
                        lang=lang,
                        country=country,
                        sort=Sort.NEWEST,
                        count=min(100, cap_per_locale - fetched_for_locale),
                        continuation_token=continuation_token
                    )
                    
                    if not result:
                        break
                        
                    stop_locale = False
                    for r in result:
                        dt = r.get("at")
                        if not dt:
                            continue
                        
                        if dt.tzinfo is None:
                            from datetime import timezone
                            dt = dt.replace(tzinfo=timezone.utc)
                        
                        if dt < since:
                            stop_locale = True
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
                        fetched_for_locale += 1
                        
                    if stop_locale or not continuation_token:
                        break
            except Exception as e:
                logger.error(f"Error fetching Play Store reviews for {locale}: {e}")
                self.errors.append(f"Error fetching Play Store reviews for {locale}: {e}")
                
        # Sort combined results by date descending and truncate to cap just in case
        all_records.sort(key=lambda x: x.created_at, reverse=True)
        return all_records[:cap]
