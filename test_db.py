from pipeline.db import execute_sql
print(execute_sql("SELECT count(*) FROM raw_records"))
print(execute_sql("SELECT count(*) FROM hypotheses"))
print(execute_sql("SELECT count(*) FROM archetype_stats"))
