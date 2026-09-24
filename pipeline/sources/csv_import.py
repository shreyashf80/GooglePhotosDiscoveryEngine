import csv
import logging
import uuid
from datetime import datetime

from pipeline.sources.base import SourceBase, hash_author
from shared.models import RawRecord
from shared.enums import Source, ItemType, Product

logger = logging.getLogger(__name__)

class CSVSource(SourceBase):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.errors = []
        self.rejected_count = 0
        
    def fetch(self, since: datetime, cap: int) -> list[RawRecord]:
        logger.info(f"Fetching CSV records from {self.file_path}")
        records = []
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    text = row.get("text", "").strip()
                    if not text:
                        continue
                        
                    dt_str = row.get("created_at")
                    dt = None
                    if dt_str:
                        try:
                            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                            if dt.tzinfo is None:
                                from datetime import timezone
                                dt = dt.replace(tzinfo=timezone.utc)
                            if dt < since:
                                continue
                        except ValueError:
                            pass
                    
                    if not dt:
                        self.rejected_count += 1
                        continue
                        
                    author = row.get("author")
                    url = row.get("url")
                    
                    id_seed = f"csv{url}" if url else f"csv{text}"
                    record_id = f"csv_{hash_author(id_seed)[:12]}"
                    
                    records.append(RawRecord(
                        record_id=record_id,
                        source=Source.CSV,
                        item_type=ItemType.POST,
                        product=Product.GOOGLE_PHOTOS,
                        url=url,
                        author_hash=hash_author(author),
                        created_at=dt,
                        text=text
                    ))
                    
                    if len(records) >= cap:
                        break
        except Exception as e:
            logger.error(f"Error reading CSV {self.file_path}: {e}")
            self.errors.append(f"Error reading CSV {self.file_path}: {e}")
            
        return records
