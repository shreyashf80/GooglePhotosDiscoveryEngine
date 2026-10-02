import json
import logging
from pydantic import BaseModel
from sqlalchemy import text

from pipeline.db import engine, execute_sql
from pipeline.llm.client import get_client
from pipeline.llm.key_pool import KeyPool
from pipeline.config import PROMPTS_DIR, GEMINI_EXTRACT_MODEL, GEMINI_API_KEYS, GEMINI_RPM_PER_KEY

logger = logging.getLogger(__name__)

class DerivedHypothesis(BaseModel):
    statement: str
    why_we_believe_it: str
    counter_evidence: str
    what_would_disprove_it: str
    primary_funnel_stage: str
    research_note: str
    research_question: str

def run_derive() -> dict:
    client = get_client("extract")
    
    with open(PROMPTS_DIR / "derive_hypotheses_v1.md", "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Get themes with >= 10 distinct authors
    themes = execute_sql("SELECT * FROM themes WHERE distinct_authors >= 10 ORDER BY rank_score DESC")
    counts = {"processed": 0, "derived": 0, "failed": 0}
    
    if not themes:
        return counts
        
    for theme in themes:
        counts["processed"] += 1
        
        # Get up to 25 reasons from signal_reasons
        reasons = execute_sql("""
            SELECT text 
            FROM signal_reasons 
            WHERE theme_id = :tid 
            LIMIT 25
        """, {"tid": theme['id']})
        reasons_sample = [r['text'] for r in reasons]
        
        # Get quotes from signals matching this theme
        quotes = execute_sql("""
            SELECT s.quote_en, r.source 
            FROM signals s
            JOIN signal_reasons sr ON sr.signal_id = s.signal_id
            JOIN raw_records r ON s.record_id = r.record_id
            WHERE sr.theme_id = :tid AND s.quote_en IS NOT NULL AND s.quote_en != ''
            GROUP BY s.quote_en, r.source
            LIMIT 8
        """, {"tid": theme['id']})
        quotes_sample = [f'"{q["quote_en"]}" ({q["source"]})' for q in quotes]
        
        # Counter signals
        counter = execute_sql("""
            SELECT s.summary_en
            FROM signals s
            JOIN signal_reasons sr ON sr.signal_id = s.signal_id
            WHERE sr.theme_id = :tid AND s.outcome IN ('found_easily', 'found_with_effort')
            LIMIT 5
        """, {"tid": theme['id']})
        counter_signals = [c['summary_en'] for c in counter]
        
        # Funnel stage mix
        funnel_rows = execute_sql("""
            SELECT funnel_stage, count(*) as c
            FROM signal_reasons
            WHERE theme_id = :tid
            GROUP BY funnel_stage
        """, {"tid": theme['id']})
        funnel_mix = {f['funnel_stage']: f['c'] for f in funnel_rows}
        
        # Outcome mix
        outcome = execute_sql("""
            SELECT s.outcome, count(DISTINCT s.signal_id) as c 
            FROM signals s
            JOIN signal_reasons sr ON sr.signal_id = s.signal_id
            WHERE sr.theme_id = :tid
            GROUP BY s.outcome
        """, {"tid": theme['id']})
        outcome_mix = {o['outcome']: o['c'] for o in outcome}
        
        # Recurring share
        recurring = execute_sql("""
            SELECT count(DISTINCT s.signal_id) as c 
            FROM signals s
            JOIN signal_reasons sr ON sr.signal_id = s.signal_id
            WHERE sr.theme_id = :tid AND s.frequency = 'recurring'
        """, {"tid": theme['id']})
        recurring_count = recurring[0]['c'] if recurring else 0
        recurring_share = recurring_count / theme['signals'] if theme['signals'] > 0 else 0
        
        # Theme data
        theme_data = {
            "theme_name": theme['name'],
            "theme_description": theme['description'],
            "scope": theme['scope'],
            "signal_count": theme['signals'],
            "distinct_authors": theme['distinct_authors'],
            "sources": theme['mixes'].get('sources', {}) if theme['mixes'] else {},
            "funnel_stage_mix": funnel_mix,
            "outcome_mix": outcome_mix,
            "recurring_share": recurring_share,
            "reasons_sample": reasons_sample,
            "quotes": quotes_sample,
            "counter_signals": counter_signals,
            "related_research": [] # omitted for now
        }
        
        prompt = prompt_template.replace("{{THEME_JSON}}", json.dumps(theme_data))
        
        try:
            res = client.generate(prompt=prompt, response_schema=DerivedHypothesis)
            
            from shared.constants import compute_hypothesis_status
            support_count = sum(c for o, c in outcome_mix.items() if o in ('gave_up', 'still_searching', 'believes_lost'))
            contradict_count = sum(c for o, c in outcome_mix.items() if o in ('found_easily', 'found_with_effort'))
            relevant_count = theme['signals']
            status = compute_hypothesis_status(support_count, contradict_count, relevant_count)

            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO hypotheses (
                            hypothesis_id, title, statement, status,
                            support_count, contradict_count, relevant_count,
                            evidence_strength, details, computed_at, 
                            origin, theme_id, rank, research_question
                        )
                        VALUES (
                            :hid, :title, :stmt, :st,
                            :sc, :cc, :rc,
                            :ev_str, :det, NOW(),
                            'data_derived', :tid, :rank, :rq
                        )
                        ON CONFLICT (hypothesis_id) DO UPDATE SET
                            title = EXCLUDED.title, statement = EXCLUDED.statement,
                            status = EXCLUDED.status, support_count = EXCLUDED.support_count,
                            contradict_count = EXCLUDED.contradict_count, relevant_count = EXCLUDED.relevant_count,
                            evidence_strength = EXCLUDED.evidence_strength,
                            origin = EXCLUDED.origin, theme_id = EXCLUDED.theme_id,
                            rank = EXCLUDED.rank, research_question = EXCLUDED.research_question
                    """),
                    {
                        "hid": f"D_{theme['id']}",
                        "title": theme['name'],
                        "stmt": res['statement'],
                        "st": status,
                        "sc": support_count,
                        "cc": contradict_count,
                        "rc": relevant_count,
                        "ev_str": theme['evidence_strength'],
                        "det": json.dumps({
                            "why": res['why_we_believe_it'],
                            "counter": res['counter_evidence'],
                            "disprove": res['what_would_disprove_it'],
                            "stage": res['primary_funnel_stage'],
                            "note": res['research_note']
                        }),
                        "tid": theme['id'],
                        "rank": theme['rank_score'],
                        "rq": res['research_question']
                    }
                )
            counts["derived"] += 1
        except Exception as e:
            logger.error(f"Error deriving hypothesis for theme {theme['id']}: {e}")
            counts["failed"] += 1
            
    return counts
