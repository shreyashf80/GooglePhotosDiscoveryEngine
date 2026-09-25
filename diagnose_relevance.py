import csv
from pipeline.db import execute_sql

def run():
    # Fetch filtered records
    sql = """
    SELECT
        record_id,
        relevance_class,
        relevance_reason,
        extra->>'subreddit' as subreddit,
        extra->>'search_term' as search_term,
        LEFT(text, 300) as text_excerpt
    FROM raw_records
    WHERE source = 'reddit' AND status IN ('filtered', 'excluded')
    """
    records = execute_sql(sql)
    
    with open('data/filter_audit.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['record_id', 'relevance_class', 'relevance_reason', 'subreddit', 'search_term', 'text_excerpt'])
        writer.writeheader()
        writer.writerows(records)
    print(f"Exported {len(records)} records to data/filter_audit.csv")

    # Group by subreddit
    sql_sub = """
    SELECT extra->>'subreddit' as subreddit, relevance_class, COUNT(*) 
    FROM raw_records 
    WHERE source = 'reddit' AND status IN ('filtered', 'excluded')
    GROUP BY extra->>'subreddit', relevance_class
    """
    print("\n--- By Subreddit ---")
    for row in execute_sql(sql_sub):
        print(f"{row['subreddit']}: {row['relevance_class']} - {row['count']}")

    # Group by search term
    sql_term = """
    SELECT extra->>'search_term' as search_term, relevance_class, COUNT(*) 
    FROM raw_records 
    WHERE source = 'reddit' AND status IN ('filtered', 'excluded')
    GROUP BY extra->>'search_term', relevance_class
    """
    print("\n--- By Search Term ---")
    for row in execute_sql(sql_term):
        print(f"{row['search_term']}: {row['relevance_class']} - {row['count']}")

if __name__ == '__main__':
    run()
