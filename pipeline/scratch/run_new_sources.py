import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

# Setup path and logging
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_pipeline")

from pipeline.config import get_time_cutoff, APIFY_TOKEN
from pipeline.sources.reddit import RedditSource
from pipeline.sources.hn import HackerNewsSource
from pipeline.sources.apple_support import AppleSupportSource
from pipeline.stages.dedup import run_dedup
from pipeline.stages.language import run_language_detection
from pipeline.stages.filter import run_filter
from pipeline.stages.extract import run_extract
from pipeline.stages.analyze import run_analyze
from pipeline.db import execute_sql, engine
import json
from sqlalchemy import text

def _upsert_records(records: list):
    if not records:
        return
    with engine.begin() as conn:
        params_list = []
        for r in records:
            extra = json.dumps(r.extra) if r.extra else None
            params_list.append({
                "id": r.record_id, "source": r.source.value, "type": r.item_type.value,
                "prod": r.product.value, "url": r.url, "hash": r.author_hash,
                "dt": r.created_at, "txt": r.text, "ext": extra
            })
        if params_list:
            conn.execute(
                text("""
                    INSERT INTO raw_records (record_id, source, item_type, product, url, author_hash, created_at, text, extra, status)
                    VALUES (:id, :source, :type, :prod, :url, :hash, :dt, :txt, :ext, 'raw')
                    ON CONFLICT (record_id) DO UPDATE SET
                        text = CASE WHEN raw_records.status = 'raw' THEN EXCLUDED.text ELSE raw_records.text END,
                        extra = EXCLUDED.extra
                """),
                params_list
            )


def main():
    cutoff = get_time_cutoff()
    
    # Skip fetch steps as they are already done
    apify_budget_remaining = 4.0 - 2.6  # Approx what was spent
    
    # 4. Dedup and Language
    logger.info("Running dedup and language detection...")
    dedup_counts = run_dedup()
    lang_counts = run_language_detection()
    logger.info(f"Dedup counts: {dedup_counts}")
    
    # 5. Filter
    logger.info("Running filter...")
    filter_counts = run_filter(limit=None)
    logger.info(f"Filter counts: {filter_counts}")
    
    # 6. Extract
    logger.info("Running extract...")
    extract_counts = run_extract(limit=None, reprocess=False)
    logger.info(f"Extract counts: {extract_counts}")
    
    # 7. Analyze
    logger.info("Running analyze...")
    analyze_counts = run_analyze()
    logger.info(f"Analyze counts: {analyze_counts}")
    
    # 8. Generate Report Data
    print("================== REPORT ==================")
    print(f"Apify Cost: ${4.0 - apify_budget_remaining:.3f} / $4.00")
    
    print("\nRecords per source:")
    rows = execute_sql("SELECT source, COUNT(*) FROM raw_records GROUP BY source")
    for r in rows:
        print(f"  {r['source']}: {r['count']}")
        
    print("\nRelevance counts per source and per search term:")
    rows = execute_sql("""
        SELECT source, COALESCE(extra->>'search_term', 'unknown') as search_term, relevance_class, COUNT(*) 
        FROM raw_records 
        WHERE relevance_class IS NOT NULL 
        GROUP BY source, extra->>'search_term', relevance_class
        ORDER BY source, search_term, relevance_class
    """)
    for r in rows:
        print(f"  {r['source']} | {r['search_term']} | {r['relevance_class']}: {r['count']}")
        
    rows = execute_sql("SELECT COUNT(*) FROM episodes")
    print(f"\nTotal episodes: {rows[0]['count'] if rows else 0}")
    
    print("\nArchetype Table:")
    rows = execute_sql("SELECT * FROM archetype_stats ORDER BY opportunity_score DESC")
    for row in rows:
        print(f"  {row['archetype']:<25s} Count: {row['episode_count']:>4d} Share: {row['share_of_episodes']:>5.1%} Sev: {row['avg_severity']:>5.1f} Stakes: {row['avg_stakes_weight']:>5.2f} Score: {row['opportunity_score']:>5.1f} Evidence: {row['evidence_strength']}")

    print("\nHypothesis Table:")
    rows = execute_sql("SELECT hypothesis_id, title, status, evidence_strength FROM hypotheses ORDER BY hypothesis_id")
    for row in rows:
        print(f"  {row['hypothesis_id']:4s} {row['title']:40s} [{row['status']}] ({row['evidence_strength']})")
        
    print("============================================")

if __name__ == "__main__":
    main()
