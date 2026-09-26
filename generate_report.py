import json
from pipeline.db import engine
from sqlalchemy import text
from collections import defaultdict

def generate():
    with engine.begin() as conn:
        # 1. Total records per source
        res = conn.execute(text("SELECT source, COUNT(*) FROM raw_records GROUP BY source"))
        source_counts = {r[0]: r[1] for r in res}

        # 2. Relevance class counts per source
        res = conn.execute(text("""
            SELECT source, relevance_class, COUNT(*) 
            FROM raw_records 
            WHERE relevance_class IS NOT NULL
            GROUP BY source, relevance_class
        """))
        rel_by_source = defaultdict(dict)
        for r in res:
            rel_by_source[r[0]][r[1]] = r[2]

        # 3. Relevance class counts per search term (for Reddit)
        res = conn.execute(text("""
            SELECT extra->>'search_term' as term, relevance_class, COUNT(*)
            FROM raw_records
            WHERE source = 'reddit' AND extra->>'search_term' IS NOT NULL AND relevance_class IS NOT NULL
            GROUP BY term, relevance_class
        """))
        rel_by_term = defaultdict(dict)
        for r in res:
            rel_by_term[r[0]][r[1]] = r[2]

        # 4. Total episodes extracted
        res = conn.execute(text("SELECT COUNT(*) FROM episodes"))
        episodes_count = res.scalar()
        
        # 5. Apify cost (count of new reddit records * 0.002)
        # Note: we might have old records, but let's count all reddit records
        # The prompt asked for "Actual Apify results used and cost".
        # We can just use the total reddit records in the DB minus 250 (which we had before).
        res = conn.execute(text("SELECT COUNT(*) FROM raw_records WHERE source = 'reddit'"))
        total_reddit = res.scalar()
        new_reddit = total_reddit - 250
        apify_cost = new_reddit * 0.002

    print(f"=== Apify Cost ===")
    print(f"New results ingested: {new_reddit}")
    print(f"Estimated Cost: ${apify_cost:.3f}")
    
    print("\n=== Records per source ===")
    for src, count in source_counts.items():
        print(f"{src}: {count}")

    print("\n=== Relevance by Source ===")
    for src, classes in rel_by_source.items():
        print(f"Source: {src}")
        for cls, count in classes.items():
            print(f"  {cls}: {count}")

    print("\n=== Relevance by Search Term (Reddit) ===")
    for term, classes in rel_by_term.items():
        print(f"Term: {term}")
        for cls, count in classes.items():
            print(f"  {cls}: {count}")

    print(f"\n=== Total Episodes Extracted ===")
    print(f"Episodes: {episodes_count}")

if __name__ == "__main__":
    generate()
