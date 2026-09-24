import logging
import uuid
from datetime import datetime

from googleapiclient.discovery import build

from pipeline.sources.base import SourceBase, hash_author
from shared.models import RawRecord
from shared.enums import Source, ItemType, Product

logger = logging.getLogger(__name__)

class YouTubeSource(SourceBase):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.errors = []
        
    def fetch(self, since: datetime, cap: int) -> list[RawRecord]:
        logger.info(f"Fetching YouTube records since {since}, cap {cap}")
        if not self.api_key:
            logger.error("YouTube API key is not set")
            return []
            
        youtube = build('youtube', 'v3', developerKey=self.api_key)
        
        # Search for videos
        queries = ["google photos search", "ask photos google", "find old photos google photos"]
        all_records = []
        
        for q in queries:
            if len(all_records) >= cap:
                break
                
            try:
                request = youtube.search().list(
                    part="id",
                    q=q,
                    type="video",
                    publishedAfter=since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    maxResults=50
                )
                response = request.execute()
                video_ids = [item["id"]["videoId"] for item in response.get("items", [])]
                
                # Fetch comments for videos
                for video_id in video_ids:
                    if len(all_records) >= cap:
                        break
                        
                    try:
                        comment_req = youtube.commentThreads().list(
                            part="snippet",
                            videoId=video_id,
                            maxResults=100,
                            textFormat="plainText"
                        )
                        
                        while comment_req and len(all_records) < cap:
                            comment_resp = comment_req.execute()
                            
                            for item in comment_resp.get("items", []):
                                snippet = item["snippet"]["topLevelComment"]["snippet"]
                                dt_str = snippet.get("publishedAt")
                                if not dt_str:
                                    continue
                                    
                                dt_str = dt_str.replace("Z", "+00:00")
                                dt = datetime.fromisoformat(dt_str)
                                if dt < since:
                                    continue
                                    
                                text = snippet.get("textDisplay", "").strip()
                                if not text:
                                    continue
                                    
                                author = snippet.get("authorDisplayName")
                                comment_id = item["id"]
                                
                                record_id = f"yt_{comment_id}" if comment_id else f"yt_{uuid.uuid4().hex[:12]}"
                                
                                all_records.append(RawRecord(
                                    record_id=record_id,
                                    source=Source.YOUTUBE,
                                    item_type=ItemType.COMMENT,
                                    product=Product.GOOGLE_PHOTOS,
                                    url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
                                    author_hash=hash_author(author),
                                    created_at=dt,
                                    text=text,
                                    extra={"video_id": video_id}
                                ))
                                
                                if len(all_records) >= cap:
                                    break
                                    
                            comment_req = youtube.commentThreads().list_next(comment_req, comment_resp)
                    except Exception as e:
                        logger.error(f"Error fetching YouTube comments for video {video_id}: {e}")
                        self.errors.append(f"Error fetching YouTube comments for video {video_id}: {e}")
            except Exception as e:
                logger.error(f"Error fetching YouTube videos for query '{q}': {e}")
                self.errors.append(f"Error fetching YouTube videos for query '{q}': {e}")
                
        all_records.sort(key=lambda x: x.created_at, reverse=True)
        return all_records[:cap]
