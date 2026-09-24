import json
from pipeline.db import execute_sql

print("--- Source Counts ---")
print(json.dumps(execute_sql("SELECT source, status, count(*) FROM raw_records GROUP BY source, status ORDER BY source"), indent=2))

print("--- Date Ranges ---")
print(json.dumps(execute_sql("SELECT min(created_at)::text, max(created_at)::text FROM raw_records"), indent=2))

print("--- Language Distribution ---")
try:
    print(json.dumps(execute_sql("SELECT extra->>'language' as language, count(*) FROM raw_records WHERE status = 'deduped' GROUP BY language ORDER BY count(*) DESC"), indent=2))
except Exception as e:
    print(f"Failed language query: {e}")

print("--- Duplicates ---")
print(json.dumps(execute_sql("SELECT relevance_reason, count(*) FROM raw_records WHERE status = 'excluded' GROUP BY relevance_reason"), indent=2))

print("--- Pipeline Runs ---")
print(json.dumps(execute_sql("SELECT source, status, errors FROM pipeline_runs WHERE status = 'failed'"), indent=2))
