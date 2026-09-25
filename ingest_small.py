from pipeline.config import get_time_cutoff
from pipeline.sources.playstore import PlayStoreSource
from pipeline.sources.appstore import AppStoreSource
from pipeline.sources.youtube import YouTubeSource
from pipeline.cli import _upsert_records
import os

from dotenv import load_dotenv
load_dotenv(".env")

appstore = AppStoreSource(os.environ["SERPAPI_KEY"])
youtube = YouTubeSource(os.environ["YOUTUBE_API_KEY"])
playstore = PlayStoreSource()

cutoff = get_time_cutoff()

def ingest(src, name, cap):
    print(f"Ingesting {name} with cap {cap}...")
    records = src.fetch(cutoff, cap)
    _upsert_records(records)
    print(f"Ingested {len(records)} from {name}")

ingest(playstore, "Play Store", 20)
ingest(appstore, "App Store", 5)
ingest(youtube, "YouTube", 2)
