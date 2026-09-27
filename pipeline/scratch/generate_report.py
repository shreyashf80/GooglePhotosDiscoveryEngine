import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

from pipeline.db import execute_sql

def print_report():
    print("=" * 40)
    print("REPORT")
    print("=" * 40)
    
    print("\n1. Raw records by source:")
    res = execute_sql("SELECT source, COUNT(*) as cnt FROM raw_records GROUP BY source ORDER BY cnt DESC")
    for r in res:
        print(f"  {r['source']:12s}: {r['cnt']}")
        
    print("\n2. Keyword matches by source:")
    res = execute_sql("SELECT source, COUNT(*) as cnt FROM raw_records WHERE keyword_hit = true GROUP BY source ORDER BY cnt DESC")
    for r in res:
        print(f"  {r['source']:12s}: {r['cnt']}")
        
    print("\n3. Class counts after filter v3:")
    res = execute_sql("SELECT relevance_class, COUNT(*) as cnt FROM raw_records WHERE relevance_class IS NOT NULL GROUP BY relevance_class ORDER BY cnt DESC")
    for r in res:
        print(f"  {r['relevance_class']:30s}: {r['cnt']}")
        
    print("\n4. Scope counts after filter v3:")
    res = execute_sql("SELECT scope, COUNT(*) as cnt FROM raw_records WHERE scope IS NOT NULL GROUP BY scope ORDER BY cnt DESC")
    for r in res:
        print(f"  {r['scope']:10s}: {r['cnt']}")

if __name__ == "__main__":
    print_report()
