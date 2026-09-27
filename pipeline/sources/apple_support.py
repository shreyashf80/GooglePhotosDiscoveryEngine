import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import uuid
import logging
from pipeline.sources.base import SourceBase, hash_author
from shared.models import RawRecord
from shared.enums import Source, ItemType, Product

logger = logging.getLogger(__name__)

class AppleSupportSource(SourceBase):
    def __init__(self):
        self.errors = []
        
    def fetch(self, since: datetime, cap: int = 40) -> list[RawRecord]:
        logger.info(f"Fetching Apple Support since {since}, cap {cap}")
        
        url = "https://discussions.apple.com/search"
        params = {
            "q": "can't find photo"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        
        records = []
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # The actual layout may vary. We'll do a best-effort scrape of search result snippets
                results = soup.select('.search-result, article')
                
                for res in results[:cap]:
                    title_elem = res.select_one('h3, .title')
                    title = title_elem.text.strip() if title_elem else ""
                    
                    body_elem = res.select_one('.content, .description')
                    body = body_elem.text.strip() if body_elem else ""
                    
                    text = f"{title}\n{body}".strip()
                    if not text:
                        continue
                        
                    link_elem = res.select_one('a')
                    href = link_elem['href'] if link_elem and 'href' in link_elem.attrs else ""
                    if href and href.startswith('/'):
                        href = "https://discussions.apple.com" + href
                        
                    records.append(RawRecord(
                        record_id=f"apl_{uuid.uuid4().hex[:10]}",
                        source=Source.COMMUNITY,
                        item_type=ItemType.POST,
                        product=Product.APPLE_PHOTOS,
                        url=href,
                        author_hash=hash_author("unknown"),
                        created_at=datetime.now(timezone.utc), # Date might not be easily parsable, default to now
                        text=text,
                        extra={"search_term": "can't find photo"}
                    ))
            else:
                self.errors.append(f"Apple Support blocked or failed: HTTP {resp.status_code}")
        except requests.RequestException as e:
            self.errors.append(f"Apple Support request failed: {e}")
            
        return records
