import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import text

from pipeline.db import engine, execute_sql
from pipeline.llm.client import GeminiClient
from pipeline.llm.key_pool import KeyPool
from pipeline.config import PROMPTS_DIR, GEMINI_EXTRACT_MODEL, GEMINI_API_KEYS, GEMINI_RPM_PER_KEY

logger = logging.getLogger(__name__)

class SignalReason(BaseModel):
    text: str
    funnel_stage: str
    specificity: str

class SignalExtraction(BaseModel):
    record_id: str
    signal_summary_en: str
    reasons: List[SignalReason]
    is_success: bool
    outcome: str
    emotional_cost: str
    frequency: str
    product: str
    platform: str
    mentions_ask_photos: bool
    quote_original: str
    quote_en: str

def run_signals(limit: Optional[int] = None) -> dict:
    pool = KeyPool(keys=GEMINI_API_KEYS, rpm_per_key=GEMINI_RPM_PER_KEY)
    client = GeminiClient(key_pool=pool, model_id=GEMINI_EXTRACT_MODEL)
    
    with open(PROMPTS_DIR / "signals_v1.md", "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Define scope mapping
    core_classes = {'specific_episode', 'general_search_complaint', 'success_or_tip', 'believes_lost'}
    adjacent_classes = {'adjacent_findability'}

    query = """
        SELECT record_id, source, created_at, lang, relevance_class, scope, text
        FROM raw_records
        WHERE relevance_class IN ('specific_episode', 'general_search_complaint', 'success_or_tip', 'believes_lost', 'adjacent_findability')
          AND NOT EXISTS (SELECT 1 FROM signals WHERE signals.record_id = raw_records.record_id)
    """
    if limit:
        query += f" LIMIT {limit}"
        
    records = execute_sql(query)
    
    counts = {"processed": 0, "extracted": 0, "failed": 0}
    if not records:
        return counts
        
    batch_size = 20
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        batch_input = []
        for r in batch:
            scope = 'core' if r['relevance_class'] in core_classes else 'adjacent'
            batch_input.append({
                "record_id": r['record_id'],
                "source": r['source'],
                "created_at": r['created_at'].isoformat() if r['created_at'] else "",
                "lang": r['lang'],
                "relevance_class": r['relevance_class'],
                "scope": scope,
                "text": r['text']
            })
            
        prompt = prompt_template.replace("{{RECORDS_JSON}}", json.dumps(batch_input))
        
        try:
            results = client.generate(prompt=prompt, response_schema=List[SignalExtraction])
            counts["processed"] += len(batch)
            
            with engine.begin() as conn:
                for res in results:
                    signal_id = res['record_id'] + "_sig"
                    conn.execute(
                        text("""
                            INSERT INTO signals (
                                signal_id, record_id, summary_en, is_success, outcome,
                                emotional_cost, frequency, product, platform,
                                mentions_ask_photos, quote_original, quote_en,
                                is_duplicate, prompt_version, model_id
                            ) VALUES (
                                :sid, :rid, :sum, :succ, :out, :emo, :freq, :prod, :plat,
                                :ask, :qo, :qe, FALSE, 'signals_v1', :model
                            ) ON CONFLICT (signal_id) DO NOTHING
                        """),
                        {
                            "sid": signal_id, "rid": res['record_id'], "sum": res['signal_summary_en'],
                            "succ": res['is_success'], "out": res['outcome'], "emo": res['emotional_cost'],
                            "freq": res['frequency'], "prod": res['product'], "plat": res['platform'],
                            "ask": res['mentions_ask_photos'], "qo": res['quote_original'], "qe": res['quote_en'],
                            "model": GEMINI_EXTRACT_MODEL
                        }
                    )
                    counts["extracted"] += 1
                    
                    for reason in res['reasons']:
                        conn.execute(
                            text("""
                                INSERT INTO signal_reasons (signal_id, text, funnel_stage, specificity)
                                VALUES (:sid, :txt, :stage, :spec)
                            """),
                            {
                                "sid": signal_id, "txt": reason['text'], 
                                "stage": reason['funnel_stage'], "spec": reason['specificity']
                            }
                        )
                        
        except Exception as e:
            logger.error(f"Error in signals batch: {e}")
            counts["failed"] += len(batch)
            
    return counts
