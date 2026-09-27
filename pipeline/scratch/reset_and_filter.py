from pipeline.db import execute_sql
import sys

# Reset the 74 records from the tournament back to 'deduped' so we can run them through Flash-Lite
execute_sql("""
    UPDATE raw_records 
    SET status = 'deduped',
        relevance_class = NULL,
        relevance_reason = NULL,
        retry_count = 0,
        last_error = NULL
    WHERE source = 'reddit' AND extra->>'search_term' IS NOT NULL AND status IN ('excluded', 'filtered', 'extract_failed')
""")
print("Records reset to deduped.")
