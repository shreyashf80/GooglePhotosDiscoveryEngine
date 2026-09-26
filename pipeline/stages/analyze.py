"""
Analyze stage — compute archetype_stats and funnel_stats.

References:
  FR-70  — evidence strength labels
  FR-80  — archetype stats: count, share, outcome distribution, top cues, etc.
  FR-81  — severity scoring
  FR-82  — stakes weight scoring
  FR-83  — opportunity score
  FR-88  — retrieval funnel stages (express, understand, evaluate, refine)
"""

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone

from pipeline.db import engine
from shared.constants import (
    SEVERITY_WEIGHTS,
    STAKES_WEIGHTS,
    compute_evidence_strength,
    compute_severity,
    compute_stakes_weight,
)
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------
# Funnel stage mapping rules
# ---------------------------------------------------------------
# An episode can hit multiple stages.

FUNNEL_STAGE_RULES = {
    "express": {
        "description": "User couldn't translate memory into a query",
        "failure_modes": set(),  # no specific failure_modes; uses cue/query logic
    },
    "understand": {
        "description": "System didn't understand the query",
        "failure_modes": {"zero_results", "wrong_results", "vocabulary_mismatch",
                          "cue_not_supported", "ask_photos_failure"},
    },
    "evaluate": {
        "description": "Too many results to scan",
        "failure_modes": {"too_many_results"},
        "workarounds": {"timeline_scroll"},
    },
    "refine": {
        "description": "No way to narrow or refine results",
        "failure_modes": {"refinement_missing"},
        # Also: 3+ queries tried
    },
}


def _episode_hits_express(episode: dict, cues: list[dict], queries: list[dict]) -> bool:
    """Express stage: vague-only cues, explicit cues_forgotten, or no queries tried."""
    # No queries tried at all
    if not queries:
        return True

    # All cues are vague
    if cues and all(c.get("precision") == "vague" for c in cues):
        return True

    # Has explicitly forgotten cues
    if episode.get("has_forgotten_cues", False):
        return True

    return False


def _episode_hits_understand(episode: dict) -> bool:
    """Understand stage: specific failure modes."""
    fm_set = set(episode.get("failure_modes", []))
    return bool(fm_set & FUNNEL_STAGE_RULES["understand"]["failure_modes"])


def _episode_hits_evaluate(episode: dict) -> bool:
    """Evaluate stage: too_many_results or timeline_scroll workaround."""
    fm_set = set(episode.get("failure_modes", []))
    wa_set = set(episode.get("workarounds", []))
    return bool(
        (fm_set & FUNNEL_STAGE_RULES["evaluate"]["failure_modes"])
        or (wa_set & FUNNEL_STAGE_RULES["evaluate"]["workarounds"])
    )


def _episode_hits_refine(episode: dict, queries: list[dict]) -> bool:
    """Refine stage: refinement_missing failure or 3+ queries tried."""
    fm_set = set(episode.get("failure_modes", []))
    if "refinement_missing" in fm_set:
        return True
    if len(queries) >= 3:
        return True
    return False


def _compute_archetype_stats(episodes: list[dict], cues_by_episode: dict,
                              queries_by_episode: dict) -> list[dict]:
    """Compute archetype_stats rows from episode data."""
    total_episodes = len(episodes)
    if total_episodes == 0:
        return []

    by_archetype = defaultdict(list)
    for ep in episodes:
        by_archetype[ep["archetype_primary"]].append(ep)

    # For opportunity score normalization, compute raw scores first
    raw_scores = {}
    stats = []

    for archetype, eps in by_archetype.items():
        count = len(eps)
        share = count / total_episodes if total_episodes > 0 else 0.0

        # Outcome distribution
        outcome_dist = Counter(ep["outcome"] for ep in eps)

        # Top cue types (from episode_cues)
        cue_counter = Counter()
        for ep in eps:
            for c in cues_by_episode.get(ep["episode_id"], []):
                cue_counter[c["cue_type"]] += 1
        top_cues = [{"cue_type": ct, "count": n} for ct, n in cue_counter.most_common(5)]

        # Top failure modes
        fm_counter = Counter()
        for ep in eps:
            for fm in ep.get("failure_modes", []):
                fm_counter[fm] += 1
        top_fm = [{"failure_mode": fm, "count": n} for fm, n in fm_counter.most_common(5)]

        # Top workarounds
        wa_counter = Counter()
        for ep in eps:
            for wa in ep.get("workarounds", []):
                wa_counter[wa] += 1
        top_wa = [{"workaround": wa, "count": n} for wa, n in wa_counter.most_common(5)]

        # Source mix
        source_mix = Counter()
        for ep in eps:
            source_mix[ep.get("source", "unknown")] += 1

        # Language mix
        lang_mix = Counter()
        for ep in eps:
            lang_mix[ep.get("lang", "unknown")] += 1

        # Category mix
        cat_mix = Counter()
        for ep in eps:
            cat_mix[ep.get("photo_category", "unknown")] += 1

        # Average severity (FR-81) — exclude 'unknown' outcomes
        severities = [compute_severity(ep["outcome"]) for ep in eps]
        valid_sevs = [s for s in severities if s is not None]
        avg_sev = sum(valid_sevs) / len(valid_sevs) if valid_sevs else 0.0

        # Average stakes weight (FR-82)
        stakes_ws = [compute_stakes_weight(ep.get("stakes", "unknown")) for ep in eps]
        avg_stakes = sum(stakes_ws) / len(stakes_ws) if stakes_ws else 1.0

        # Raw opportunity score (FR-83)
        raw_opp = share * avg_sev * avg_stakes
        raw_scores[archetype] = raw_opp

        stats.append({
            "archetype": archetype,
            "episode_count": count,
            "share_of_episodes": round(share, 4),
            "outcome_distribution": dict(outcome_dist),
            "top_cue_types": top_cues,
            "top_failure_modes": top_fm,
            "top_workarounds": top_wa,
            "source_mix": dict(source_mix),
            "language_mix": dict(lang_mix),
            "category_mix": dict(cat_mix),
            "avg_severity": round(avg_sev, 2),
            "avg_stakes_weight": round(avg_stakes, 2),
            "opportunity_score": 0.0,  # normalized below
            "evidence_strength": compute_evidence_strength(count),
        })

    # Normalize opportunity scores to 0-100
    max_raw = max(raw_scores.values()) if raw_scores else 1.0
    if max_raw > 0:
        for s in stats:
            s["opportunity_score"] = round(
                (raw_scores[s["archetype"]] / max_raw) * 100, 1
            )

    return stats


def _compute_funnel_stats(episodes: list[dict], cues_by_episode: dict,
                           queries_by_episode: dict,
                           general_failure_modes: list[list[str]]) -> list[dict]:
    """Compute funnel_stats for the four retrieval stages."""
    stage_episodes = {
        "express": [],
        "understand": [],
        "evaluate": [],
        "refine": [],
    }

    for ep in episodes:
        eid = ep["episode_id"]
        cues = cues_by_episode.get(eid, [])
        queries = queries_by_episode.get(eid, [])

        if _episode_hits_express(ep, cues, queries):
            stage_episodes["express"].append(ep)
        if _episode_hits_understand(ep):
            stage_episodes["understand"].append(ep)
        if _episode_hits_evaluate(ep):
            stage_episodes["evaluate"].append(ep)
        if _episode_hits_refine(ep, queries):
            stage_episodes["refine"].append(ep)

    # Count general complaint failure modes that map to each stage
    general_stage_counts = {
        "express": 0,
        "understand": 0,
        "evaluate": 0,
        "refine": 0,
    }
    for gfm_list in general_failure_modes:
        gfm_set = set(gfm_list) if gfm_list else set()
        if gfm_set & {"cue_not_supported"}:
            general_stage_counts["express"] += 1
        if gfm_set & FUNNEL_STAGE_RULES["understand"]["failure_modes"]:
            general_stage_counts["understand"] += 1
        if gfm_set & {"too_many_results"}:
            general_stage_counts["evaluate"] += 1
        if gfm_set & {"refinement_missing"}:
            general_stage_counts["refine"] += 1

    results = []
    for stage_name in ["express", "understand", "evaluate", "refine"]:
        eps = stage_episodes[stage_name]
        count = len(eps)

        # Gave-up rate
        gave_up = sum(1 for ep in eps if ep["outcome"] in ("gave_up", "still_searching"))
        gave_up_rate = gave_up / count if count > 0 else 0.0

        # Average severity
        severities = [compute_severity(ep["outcome"]) for ep in eps]
        valid_sevs = [s for s in severities if s is not None]
        avg_sev = sum(valid_sevs) / len(valid_sevs) if valid_sevs else 0.0

        results.append({
            "stage": stage_name,
            "episode_count": count,
            "general_complaint_count": general_stage_counts[stage_name],
            "gave_up_rate": round(gave_up_rate, 3),
            "avg_severity": round(avg_sev, 2),
            "evidence_strength": compute_evidence_strength(count),
            "details": json.dumps({
                "description": FUNNEL_STAGE_RULES[stage_name]["description"],
            }),
        })

    return results


def run_analyze() -> dict:
    """Run the full analysis stage: archetype_stats and funnel_stats.

    Returns summary counts.
    """
    now = datetime.now(timezone.utc)

    # Load all episodes with their parent record info
    with engine.begin() as conn:
        episode_rows = conn.execute(text("""
            SELECT e.episode_id, e.record_id, e.archetype_primary, e.archetype_secondary,
                   e.outcome, e.stakes, e.photo_category, e.photo_origin,
                   e.failure_modes, e.workarounds, e.extraction_confidence,
                   r.source, r.lang
            FROM episodes e
            JOIN raw_records r ON e.record_id = r.record_id
        """)).fetchall()

        # Load cues
        cue_rows = conn.execute(text(
            "SELECT episode_id, cue_type, value, precision FROM episode_cues"
        )).fetchall()

        # Load queries
        query_rows = conn.execute(text(
            "SELECT episode_id, query_text, query_style, position FROM episode_queries ORDER BY position"
        )).fetchall()

        # Load forgotten cues per episode (just existence check)
        forgotten_rows = conn.execute(text(
            "SELECT DISTINCT episode_id FROM episode_forgotten"
        )).fetchall()

        # Load general_failure_modes from general_search_complaint records
        general_rows = conn.execute(text("""
            SELECT general_failure_modes
            FROM raw_records
            WHERE relevance_class = 'general_search_complaint'
              AND general_failure_modes IS NOT NULL
              AND array_length(general_failure_modes, 1) > 0
        """)).fetchall()

    # Build lookup dicts
    episodes = []
    forgotten_set = {r.episode_id for r in forgotten_rows}

    for r in episode_rows:
        episodes.append({
            "episode_id": r.episode_id,
            "record_id": r.record_id,
            "archetype_primary": r.archetype_primary,
            "archetype_secondary": r.archetype_secondary,
            "outcome": r.outcome,
            "stakes": r.stakes,
            "photo_category": r.photo_category,
            "photo_origin": r.photo_origin,
            "failure_modes": list(r.failure_modes) if r.failure_modes else [],
            "workarounds": list(r.workarounds) if r.workarounds else [],
            "extraction_confidence": r.extraction_confidence,
            "source": r.source,
            "lang": r.lang,
            "has_forgotten_cues": r.episode_id in forgotten_set,
        })

    cues_by_episode = defaultdict(list)
    for c in cue_rows:
        cues_by_episode[c.episode_id].append({
            "cue_type": c.cue_type,
            "value": c.value,
            "precision": c.precision,
        })

    queries_by_episode = defaultdict(list)
    for q in query_rows:
        queries_by_episode[q.episode_id].append({
            "query_text": q.query_text,
            "query_style": q.query_style,
            "position": q.position,
        })

    general_failure_modes = [
        list(r.general_failure_modes) if r.general_failure_modes else []
        for r in general_rows
    ]

    logger.info(f"Analyze: {len(episodes)} episodes, {len(general_failure_modes)} general complaints")

    # Compute archetype stats
    arch_stats = _compute_archetype_stats(episodes, cues_by_episode, queries_by_episode)

    # Compute funnel stats
    funnel_stats = _compute_funnel_stats(episodes, cues_by_episode, queries_by_episode,
                                          general_failure_modes)

    # Write to DB
    with engine.begin() as conn:
        # Upsert archetype_stats
        conn.execute(text("DELETE FROM archetype_stats"))
        for s in arch_stats:
            conn.execute(text("""
                INSERT INTO archetype_stats
                    (archetype, episode_count, share_of_episodes, outcome_distribution,
                     top_cue_types, top_failure_modes, top_workarounds,
                     source_mix, language_mix, category_mix,
                     avg_severity, avg_stakes_weight, opportunity_score,
                     evidence_strength, computed_at)
                VALUES
                    (:archetype, :episode_count, :share_of_episodes, :outcome_distribution,
                     :top_cue_types, :top_failure_modes, :top_workarounds,
                     :source_mix, :language_mix, :category_mix,
                     :avg_severity, :avg_stakes_weight, :opportunity_score,
                     :evidence_strength, :computed_at)
            """), {
                "archetype": s["archetype"],
                "episode_count": s["episode_count"],
                "share_of_episodes": s["share_of_episodes"],
                "outcome_distribution": json.dumps(s["outcome_distribution"]),
                "top_cue_types": json.dumps(s["top_cue_types"]),
                "top_failure_modes": json.dumps(s["top_failure_modes"]),
                "top_workarounds": json.dumps(s["top_workarounds"]),
                "source_mix": json.dumps(s["source_mix"]),
                "language_mix": json.dumps(s["language_mix"]),
                "category_mix": json.dumps(s["category_mix"]),
                "avg_severity": s["avg_severity"],
                "avg_stakes_weight": s["avg_stakes_weight"],
                "opportunity_score": s["opportunity_score"],
                "evidence_strength": s["evidence_strength"],
                "computed_at": now,
            })

        # Upsert funnel_stats
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
                "stage": f["stage"],
                "episode_count": f["episode_count"],
                "general_complaint_count": f["general_complaint_count"],
                "gave_up_rate": f["gave_up_rate"],
                "avg_severity": f["avg_severity"],
                "evidence_strength": f["evidence_strength"],
                "details": f["details"],
                "computed_at": now,
            })

    logger.info(f"Analyze complete: {len(arch_stats)} archetypes, {len(funnel_stats)} funnel stages written")

    return {
        "archetypes_written": len(arch_stats),
        "funnel_stages_written": len(funnel_stats),
        "total_episodes": len(episodes),
    }
