import asyncio
import sys
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

from pipeline.db import execute_sql
from pipeline.stages.filter import run_filter

def reprocess():
    print("Marking records with text as deduped for reprocessing...")
    execute_sql("UPDATE raw_records SET status = 'deduped' WHERE text IS NOT NULL AND text != ''")
    
    print("Running filter v3...")
    counts = run_filter()
    print("Filter results:", counts)
    
if __name__ == "__main__":
    reprocess()
