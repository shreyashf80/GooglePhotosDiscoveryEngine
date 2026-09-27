import json
import logging
from pipeline.db import engine
from pipeline.llm.client import GeminiClient
from pipeline.llm.key_pool import KeyPool
from pipeline.config import GEMINI_API_KEYS, GEMINI_RPM_PER_KEY
from pipeline.stages.filter import FilterResultItem, PROMPTS_DIR
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)

with engine.begin() as conn:
    # 1. Get 10 records that were excluded
    res = conn.execute(text("""
        SELECT record_id, text, relevance_class, relevance_reason, extra->>'search_term' as search_term, lang, source
        FROM raw_records
        WHERE status = 'excluded' AND source = 'reddit'
        LIMIT 10
    """))
    records = res.fetchall()
    
    # 2. Count empty, [removed], [deleted], title only
    # Text is "Title\nBody". We can check if it ends with [removed] or [deleted] or has no \n (title only)
    res_stats = conn.execute(text("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN text IS NULL OR text = '' THEN 1 ELSE 0 END) as empty,
            SUM(CASE WHEN text LIKE '%[removed]' THEN 1 ELSE 0 END) as removed,
            SUM(CASE WHEN text LIKE '%[deleted]' THEN 1 ELSE 0 END) as deleted,
            SUM(CASE WHEN text NOT LIKE '%\n%' THEN 1 ELSE 0 END) as title_only
        FROM raw_records
        WHERE source = 'reddit'
    """))
    stats = res_stats.fetchone()

print(f"\n--- Statistics on all Reddit records (Total: {stats.total}) ---")
print(f"Empty text: {stats.empty}")
print(f"Ends with [removed]: {stats.removed}")
print(f"Ends with [deleted]: {stats.deleted}")
print(f"Title only (no newline): {stats.title_only}")

print("\n--- 10 Sample Records (Original) ---")
for r in records:
    txt = (r.text or "").replace('\n', ' ')[:300]
    print(f"\nID: {r.record_id}")
    print(f"Search Term: {r.search_term}")
    print(f"Text (first 300): {txt}")
    print(f"Class: {r.relevance_class}")
    print(f"Reason: {r.relevance_reason}")

# 3. Rerun with gemini-3.8-flash
print("\n--- Rerunning with gemini-3.8-flash ---")
key_pool = KeyPool(keys=GEMINI_API_KEYS, rpm_per_key=GEMINI_RPM_PER_KEY)
client = GeminiClient(key_pool=key_pool, model_id="gemini-3.8-flash")

prompt_path = PROMPTS_DIR / "filter_v1.md"
prompt_template = prompt_path.read_text()

to_llm = [
    {
        "record_id": r.record_id,
        "source": r.source,
        "lang": r.lang or "en",
        "text": r.text
    }
    for r in records
]

records_json = json.dumps(to_llm, ensure_ascii=False, indent=2)
prompt = prompt_template.replace("{{RECORDS_JSON}}", records_json)

response = client.generate(
    prompt=prompt,
    response_schema=list[FilterResultItem],
    temperature=0.1
)

results_list = response if isinstance(response, list) else response.get("results", response)
new_results_by_id = {}
for item in results_list:
    if isinstance(item, dict):
        new_results_by_id[item["record_id"]] = item
    else:
        new_results_by_id[item.record_id] = item

print("\n--- Comparison (Flash-Lite vs 3.8-Flash) ---")
for r in records:
    old_class = r.relevance_class
    old_reason = r.relevance_reason
    
    new_res = new_results_by_id.get(r.record_id)
    if new_res:
        if isinstance(new_res, dict):
            new_class = new_res.get("relevance_class")
            new_reason = new_res.get("reason")
        else:
            new_class = new_res.relevance_class
            new_reason = new_res.reason
    else:
        new_class = "MISSING"
        new_reason = "MISSING"
        
    print(f"\nID: {r.record_id}")
    print(f"Text (first 100): {(r.text or '').replace(chr(10), ' ')[:100]}")
    print(f"Old (Flash-Lite): {old_class} | {old_reason}")
    print(f"New (3.8-Flash): {new_class} | {new_reason}")
