import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone

from pipeline.db import engine
from pipeline.stages.signals import run_signals
from pipeline.stages.embed import run_embed
from pipeline.stages.themes import run_themes
from pipeline.stages.derive import run_derive
from shared.constants import compute_gap_score
from sqlalchemy import text
import yaml

logger = logging.getLogger(__name__)

def _compute_funnel_stats(reasons_with_scope) -> list[dict]:
    # reasons_with_scope is a list of dicts: {'funnel_stage': x, 'scope': y, 'outcome': z}
    stats = []
    
    stages = ["express", "understand", "evaluate", "refine", "outside_search"]
    
    for scope in ['core', 'adjacent']:
        scope_reasons = [r for r in reasons_with_scope if r['scope'] == scope]
        for stage in stages:
            stage_reasons = [r for r in scope_reasons if r['funnel_stage'] == stage]
            count = len(stage_reasons)
            if count == 0:
                continue
                
            gave_up = sum(1 for r in stage_reasons if r['outcome'] in ('gave_up', 'still_searching'))
            gave_up_rate = gave_up / count if count > 0 else 0.0
            
            # Simple average severity calculation
            severity_map = {'gave_up': 3.0, 'still_searching': 2.5, 'believes_lost': 3.0, 'found_with_effort': 2.0, 'found_easily': 1.0}
            severities = [severity_map.get(r['outcome'], 0) for r in stage_reasons if r['outcome'] in severity_map]
            avg_sev = sum(severities) / len(severities) if severities else 0.0
            
            if count >= 30:
                ev_str = "strong"
            elif count >= 15:
                ev_str = "directional"
            else:
                ev_str = "anecdotal"
                
            stats.append({
                "stage": stage,
                "scope": scope,
                "episode_count": count,
                "general_complaint_count": 0, # Placeholder
                "gave_up_rate": round(gave_up_rate, 3),
                "avg_severity": round(avg_sev, 2),
                "evidence_strength": ev_str,
                "details": json.dumps({"description": f"{stage} in {scope}"}),
            })
    return stats

def _compute_segment_stats(signals_with_meta):
    stats = []
    dimensions = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    
    for sig in signals_with_meta:
        theme = sig["theme_name"] if sig["theme_name"] else "Unknown"
        dimensions["source"][sig.get("source") or "unknown"][theme].append(sig)
        dimensions["product"][sig.get("product") or "unknown"][theme].append(sig)
        dimensions["class"][sig.get("relevance_class") or "unknown"][theme].append(sig)
        dimensions["language"][sig.get("lang") or "unknown"][theme].append(sig)
            
    for dim_name, dim_values in dimensions.items():
        for val, themes in dim_values.items():
            for theme, sigs in themes.items():
                count = len(sigs)
                outcomes = Counter(s["outcome"] for s in sigs)
                stats.append({
                    "dimension": dim_name,
                    "value": val,
                    "archetype": theme,  # using archetype column for theme
                    "episode_count": count,
                    "outcome_mix": dict(outcomes)
                })
    return stats

def run_analyze() -> dict:
    now = datetime.now(timezone.utc)
    
    logger.info("Running Signals extraction...")
    counts_signals = run_signals()
    logger.info(f"Signals extracted: {counts_signals}")
    
    logger.info("Running Embedding (includes dedup)...")
    counts_embed = run_embed()
    logger.info(f"Embeddings generated: {counts_embed}")
    
    logger.info("Running Themes clustering...")
    counts_themes = run_themes()
    logger.info(f"Themes generated: {counts_themes}")
    
    logger.info("Running Hypothesis Derivation...")
    counts_derive = run_derive()
    logger.info(f"Hypotheses derived: {counts_derive}")

    # Fetch data for Funnel and Segments
    with engine.begin() as conn:
        reason_rows = conn.execute(text("""
            SELECT sr.funnel_stage, r.scope, s.outcome
            FROM signal_reasons sr
            JOIN signals s ON sr.signal_id = s.signal_id
            JOIN raw_records r ON s.record_id = r.record_id
            WHERE s.is_duplicate = FALSE
        """)).fetchall()
        
        signal_rows = conn.execute(text("""
            SELECT s.signal_id, s.outcome, s.product, r.source, r.relevance_class, r.lang,
                   (SELECT t.name FROM themes t JOIN signal_reasons sr2 ON sr2.theme_id = t.id WHERE sr2.signal_id = s.signal_id LIMIT 1) as theme_name
            FROM signals s
            JOIN raw_records r ON s.record_id = r.record_id
            WHERE s.is_duplicate = FALSE
        """)).fetchall()

    reasons_with_scope = [{'funnel_stage': r.funnel_stage, 'scope': r.scope, 'outcome': r.outcome} for r in reason_rows]
    signals_with_meta = [dict(r._mapping) for r in signal_rows]

    funnel_stats = _compute_funnel_stats(reasons_with_scope)
    segment_stats = _compute_segment_stats(signals_with_meta)

    # Note: Gap matrix depends on cue_stats which comes from episodes. 
    # We keep the old logic for cues / episodes just by recalculating gap_scores if needed, but not recreating cue_stats from scratch since extract v2 still generates episodes.
    # The requirement is: "Extract v2 - Keep, narrow... gap matrix, cue stats, capability reference... keep"
    # We won't recompute cue_stats here, assume they are already computed by earlier `analyze` or we just leave them.
    # We'll just overwrite funnel and segment stats.
    
    with engine.begin() as conn:
        # Funnel Stats (using stage for scope if we need to shoehorn into existing schema, wait, funnel_stats doesn't have scope column, I'll store scope in details or append to stage)
        conn.execute(text("DELETE FROM funnel_stats"))
        for f in funnel_stats:
            conn.execute(text("""
                INSERT INTO funnel_stats
                    (stage, episode_count, general_complaint_count,
                     gave_up_rate, avg_severity, evidence_strength, details, computed_at)
                VALUES
                    (:stage, :episode_count, :general_complaint_count,
                     :gave_up_rate, :avg_severity, :evidence_strength, :details, :computed_at)
            """), {
                "stage": f["stage"] + "_" + f["scope"], "episode_count": f["episode_count"], "general_complaint_count": f["general_complaint_count"],
                "gave_up_rate": f["gave_up_rate"], "avg_severity": f["avg_severity"], "evidence_strength": f["evidence_strength"],
                "details": f["details"], "computed_at": now,
            })

        conn.execute(text("DELETE FROM segment_stats"))
        for ss in segment_stats:
            conn.execute(text("""
                INSERT INTO segment_stats (dimension, value, archetype, episode_count, outcome_mix)
                VALUES (:d, :v, :a, :c, :om)
            """), {
                "d": ss["dimension"], "v": ss["value"], "a": ss["archetype"], "c": ss["episode_count"], "om": json.dumps(ss["outcome_mix"])
            })

    return {
        "signals_extracted": counts_signals.get("extracted", 0),
        "themes_created": counts_themes.get("themes_created", 0),
        "hypotheses_derived": counts_derive.get("derived", 0),
        "funnel_stages_written": len(funnel_stats),
        "segments_written": len(segment_stats)
    }

if __name__ == "__main__":
    run_analyze()
