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

def _compute_cue_stats(episodes: list[dict], cues_by_episode: dict, forgotten_cues: list[dict]) -> list[dict]:
    total = len(episodes)
    if total == 0:
        return []
    cue_types = set()
    for eid, cues in cues_by_episode.items():
        for c in cues:
            cue_types.add(c["cue_type"])
    for fc in forgotten_cues:
        cue_types.add(fc["cue_type"])
    stats = []
    for ct in sorted(cue_types):
        eps_with_cue = [ep for ep in episodes if any(c["cue_type"] == ct for c in cues_by_episode.get(ep["episode_id"], []))]
        remembered_share = len(eps_with_cue) / total if total > 0 else 0.0
        precisions = [c["precision"] for ep in eps_with_cue for c in cues_by_episode.get(ep["episode_id"], []) if c["cue_type"] == ct]
        total_p = len(precisions)
        p_exact = precisions.count("exact") / total_p if total_p else 0.0
        p_approx = precisions.count("approximate") / total_p if total_p else 0.0
        p_vague = precisions.count("vague") / total_p if total_p else 0.0
        forgotten_count = sum(1 for fc in forgotten_cues if fc["cue_type"] == ct)
        
        eps_failed = [ep for ep in eps_with_cue if ep["outcome"] in ("gave_up", "still_searching", "found_with_effort")]
        failure_rate = len(eps_failed) / len(eps_with_cue) if eps_with_cue else 0.0
        
        stats.append({
            "cue_type": ct,
            "remembered_share": remembered_share,
            "precision_exact": p_exact,
            "precision_approximate": p_approx,
            "precision_vague": p_vague,
            "forgotten_count": forgotten_count,
            "failure_rate": failure_rate
        })
    return stats

def run_analyze(run_substages: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    
    counts_signals = {}
    counts_embed = {}
    counts_themes = {}
    counts_derive = {}

    if run_substages:
        logger.info("Running Embedding (includes dedup)...")
        counts_embed = run_embed()
        logger.info(f"Embeddings generated: {counts_embed}")
        
        logger.info("Running Themes clustering...")
        counts_themes = run_themes()
        logger.info(f"Themes generated: {counts_themes}")
        
        logger.info("Running Hypothesis Derivation...")
        counts_derive = run_derive()
        logger.info(f"Hypotheses derived: {counts_derive}")

    # Fetch data for Funnel, Segments, and Cues
    with engine.begin() as conn:
        reason_rows = conn.execute(text("""
            SELECT sr.funnel_stage, r.scope, s.outcome, sr.theme_id
            FROM signal_reasons sr
            JOIN signals s ON sr.signal_id = s.signal_id
            JOIN raw_records r ON s.record_id = r.record_id
            WHERE s.is_duplicate = FALSE
        """)).fetchall()
        
        signal_rows = conn.execute(text("""
            SELECT s.signal_id, s.outcome, 'Google Photos' as product, r.source, r.relevance_class, r.lang,
                   (SELECT t.name FROM themes t JOIN signal_reasons sr ON sr.theme_id = t.id WHERE sr.signal_id = s.signal_id LIMIT 1) as theme_name
            FROM signals s
            JOIN raw_records r ON s.record_id = r.record_id
            WHERE s.is_duplicate = FALSE
        """)).fetchall()

        # Episodes and cues for gap matrix
        ep_rows = conn.execute(text("""
            SELECT episode_id, outcome FROM episodes WHERE is_duplicate = FALSE
        """)).fetchall()
        cue_rows = conn.execute(text("""
            SELECT episode_id, cue_type, precision FROM episode_cues
        """)).fetchall()
        forgotten_rows = conn.execute(text("""
            SELECT episode_id, cue_type FROM episode_forgotten
        """)).fetchall()
        caps_rows = conn.execute(text("""
            SELECT cue_type, searchable FROM capability_reference
        """)).fetchall()

    caps = {r.cue_type: r.searchable for r in caps_rows}
    episodes = [dict(r._mapping) for r in ep_rows]
    cues_by_episode = defaultdict(list)
    for c in cue_rows:
        cues_by_episode[c.episode_id].append({"cue_type": c.cue_type, "precision": c.precision})
    forgotten_cues = [dict(r._mapping) for r in forgotten_rows]

    cue_stats = _compute_cue_stats(episodes, cues_by_episode, forgotten_cues)

    reasons_with_scope = [{'funnel_stage': r.funnel_stage, 'scope': r.scope, 'outcome': r.outcome, 'theme_id': r.theme_id} for r in reason_rows]
    signals_with_meta = [dict(r._mapping) for r in signal_rows]

    funnel_stats = _compute_funnel_stats(reasons_with_scope)
    segment_stats = _compute_segment_stats(signals_with_meta)
    
    # Calculate funnel stages per theme
    theme_funnels = defaultdict(Counter)
    for r in reasons_with_scope:
        if r['theme_id']:
            theme_funnels[r['theme_id']][r['funnel_stage']] += 1
    
    with engine.begin() as conn:
        for theme_id, counts in theme_funnels.items():
            row = conn.execute(text("SELECT mixes FROM themes WHERE id = :id"), {"id": theme_id}).fetchone()
            if row:
                mixes = row.mixes or {}
                if isinstance(mixes, str):
                    mixes = json.loads(mixes)
                mixes["funnel_stages"] = dict(counts)
                conn.execute(text("UPDATE themes SET mixes = :mixes WHERE id = :id"), {"mixes": json.dumps(mixes), "id": theme_id})
                
        # Funnel Stats
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

        # Segment Stats
        conn.execute(text("DELETE FROM segment_stats"))
        for ss in segment_stats:
            conn.execute(text("""
                INSERT INTO segment_stats (dimension, value, archetype, episode_count, outcome_mix)
                VALUES (:d, :v, :a, :c, :om)
            """), {
                "d": ss["dimension"], "v": ss["value"], "a": ss["archetype"], "c": ss["episode_count"], "om": json.dumps(ss["outcome_mix"])
            })

        # Cue Stats / Gap Matrix
        if cue_stats:
            conn.execute(text("DELETE FROM cue_stats"))
            for c in cue_stats:
                searchable = caps.get(c["cue_type"], "not_verified")
                gap = compute_gap_score(c["remembered_share"], searchable) if searchable != "not_verified" else None
                conn.execute(text("""
                    INSERT INTO cue_stats (cue_type, remembered_share, precision_exact, precision_approximate, precision_vague, forgotten_count, failure_rate, gap_score, computed_at)
                    VALUES (:ct, :rs, :pe, :pa, :pv, :fc, :fr, :gs, :ca)
                """), {
                    "ct": c["cue_type"], "rs": c["remembered_share"], "pe": c["precision_exact"], "pa": c["precision_approximate"], "pv": c["precision_vague"],
                    "fc": c["forgotten_count"], "fr": c["failure_rate"], "gs": gap, "ca": now
                })

    return {
        "signals_extracted": counts_signals.get("extracted", 0),
        "themes_created": counts_themes.get("themes_created", 0),
        "hypotheses_derived": counts_derive.get("derived", 0),
        "funnel_stages_written": len(funnel_stats),
        "segments_written": len(segment_stats),
        "cues_written": len(cue_stats)
    }

if __name__ == "__main__":
    run_analyze()
