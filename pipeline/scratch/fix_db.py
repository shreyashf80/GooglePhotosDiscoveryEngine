import sys
import csv
from pipeline.db import execute_sql

# Reset retry_count
execute_sql("""
    UPDATE raw_records 
    SET retry_count = 0 
    WHERE last_error LIKE '%503%' OR last_error LIKE '%Rate limit%'
""")

# Export CSV
rows = execute_sql("""
    SELECT 
        relevance_class,
        relevance_reason,
        extra->>'community_search' as subreddit,
        extra->>'search_term' as search_term,
        LEFT(text, 300) as text_preview
    FROM raw_records
    WHERE source = 'reddit' AND relevance_class IS NOT NULL
""")
with open('data/filter_audit.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['relevance_class', 'reason', 'subreddit', 'search_term', 'text_preview'])
    for row in rows:
        writer.writerow([
            row.get('relevance_class', ''),
            row.get('relevance_reason', ''),
            row.get('subreddit', ''),
            row.get('search_term', ''),
            row.get('text_preview', '').replace('\n', ' ')
        ])

# Volume stats
all_rows = execute_sql("""
    SELECT 
        extra->>'search_term' as search_term,
        status,
        COUNT(*) as count
    FROM raw_records
    WHERE source = 'reddit' AND extra->>'search_term' IS NOT NULL
    GROUP BY 1, 2
""")
stats = {}
for r in all_rows:
    st = r['search_term']
    if st not in stats:
        stats[st] = {'deduped': 0, 'filtered': 0, 'excluded': 0, 'extracted': 0, 'failed': 0, 'duplicate': 0}
    stats[st][r['status']] = r['count']

print(f"{'Search Term':<45} | {'Ingested':<8} | {'Dupes':<6} | {'Deduped':<8}")
print("-" * 75)
for st, counts in stats.items():
    dupes = counts.get('duplicate', 0)
    deduped = sum([counts.get(s, 0) for s in ['deduped', 'filtered', 'excluded', 'extracted', 'failed']])
    ingested = dupes + deduped
    print(f"{st:<45} | {ingested:<8} | {dupes:<6} | {deduped:<8}")

