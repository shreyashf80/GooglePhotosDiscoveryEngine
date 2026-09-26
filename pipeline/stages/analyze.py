import json
import logging
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone

from pipeline.db import engine
from shared.constants import (
    SEVERITY_WEIGHTS,
    STAKES_WEIGHTS,
    compute_evidence_strength,
    compute_severity,
    compute_stakes_weight,
    compute_hypothesis_status,
    compute_gap_score
)
from shared.enums import PhotoCategory
from sqlalchemy import text
import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------
# Funnel stage mapping rules
# ---------------------------------------------------------------
FUNNEL_STAGE_RULES = {
    "express": {
        "description": "User couldn't translate memory into a query",
        "failure_modes": set(),
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
    },
}

def _episode_hits_express(episode: dict, cues: list[dict], queries: list[dict]) -> bool:
    if cues and all(c.get("precision") == "vague" for c in cues):
        return True
    if episode.get("has_forgotten_cues", False):
        return True
    text_content = (episode.get("quote_en", "") + " " + episode.get("summary_en", "")).lower()
    if "didn't know what to search" in text_content or "don't know what to search" in text_content:
        return True
    return False

def _episode_hits_understand(episode: dict) -> bool:
    fm_set = set(episode.get("failure_modes", []))
    return bool(fm_set & FUNNEL_STAGE_RULES["understand"]["failure_modes"])

def _episode_hits_evaluate(episode: dict) -> bool:
    fm_set = set(episode.get("failure_modes", []))
    wa_set = set(episode.get("workarounds", []))
    return bool(
        (fm_set & FUNNEL_STAGE_RULES["evaluate"]["failure_modes"])
        or (wa_set & FUNNEL_STAGE_RULES["evaluate"]["workarounds"])
    )

def _episode_hits_refine(episode: dict, queries: list[dict]) -> bool:
    fm_set = set(episode.get("failure_modes", []))
    if "refinement_missing" in fm_set:
        return True
    if len(queries) >= 3:
        return True
    return False

def _compute_archetype_stats(episodes: list[dict], cues_by_episode: dict,
                              queries_by_episode: dict) -> list[dict]:
    total_episodes = len(episodes)
    if total_episodes == 0:
        return []
    by_archetype = defaultdict(list)
    for ep in episodes:
        by_archetype[ep["archetype_primary"]].append(ep)
    raw_scores = {}
    stats = []
    for archetype, eps in by_archetype.items():
        count = len(eps)
        share = count / total_episodes if total_episodes > 0 else 0.0
        outcome_dist = Counter(ep["outcome"] for ep in eps)
        cue_counter = Counter()
        for ep in eps:
            for c in cues_by_episode.get(ep["episode_id"], []):
                cue_counter[c["cue_type"]] += 1
        top_cues = [{"cue_type": ct, "count": n} for ct, n in cue_counter.most_common(5)]
        fm_counter = Counter()
        for ep in eps:
            for fm in ep.get("failure_modes", []):
                fm_counter[fm] += 1
        top_fm = [{"failure_mode": fm, "count": n} for fm, n in fm_counter.most_common(5)]
        wa_counter = Counter()
        for ep in eps:
            for wa in ep.get("workarounds", []):
                wa_counter[wa] += 1
        top_wa = [{"workaround": wa, "count": n} for wa, n in wa_counter.most_common(5)]
        source_mix = Counter(ep.get("source", "unknown") for ep in eps)
        lang_mix = Counter(ep.get("lang", "unknown") for ep in eps)
        cat_mix = Counter(ep.get("photo_category", "unknown") for ep in eps)
        severities = [compute_severity(ep["outcome"]) for ep in eps]
        valid_sevs = [s for s in severities if s is not None]
        avg_sev = sum(valid_sevs) / len(valid_sevs) if valid_sevs else 0.0
        stakes_ws = [compute_stakes_weight(ep.get("stakes", "unknown")) for ep in eps]
        avg_stakes = sum(stakes_ws) / len(stakes_ws) if stakes_ws else 1.0
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
            "opportunity_score": 0.0,
            "evidence_strength": compute_evidence_strength(count),
        })
    max_raw = max(raw_scores.values()) if raw_scores else 1.0
    if max_raw > 0:
        for s in stats:
            s["opportunity_score"] = round((raw_scores[s["archetype"]] / max_raw) * 100, 1)
    return stats

def _compute_funnel_stats(episodes: list[dict], cues_by_episode: dict,
                           queries_by_episode: dict,
                           general_failure_modes: list[list[str]]) -> list[dict]:
    stage_episodes = {"express": [], "understand": [], "evaluate": [], "refine": []}
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
    general_stage_counts = {"express": 0, "understand": 0, "evaluate": 0, "refine": 0}
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
        gave_up = sum(1 for ep in eps if ep["outcome"] in ("gave_up", "still_searching"))
        gave_up_rate = gave_up / count if count > 0 else 0.0
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
            "details": json.dumps({"description": FUNNEL_STAGE_RULES[stage_name]["description"]}),
        })
    return results

def _compute_cue_stats(episodes, cues_by_episode, forgotten_cues):
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
    for ct in cue_types:
        eps_with_cue = [ep for ep in episodes if any(c["cue_type"] == ct for c in cues_by_episode.get(ep["episode_id"], []))]
        remembered_share = len(eps_with_cue) / total
        precisions = [c["precision"] for ep in eps_with_cue for c in cues_by_episode.get(ep["episode_id"], []) if c["cue_type"] == ct]
        total_p = len(precisions)
        p_exact = precisions.count("exact") / total_p if total_p else 0.0
        p_approx = precisions.count("approximate") / total_p if total_p else 0.0
        p_vague = precisions.count("vague") / total_p if total_p else 0.0
        forgotten_count = sum(1 for fc in forgotten_cues if fc["cue_type"] == ct)
        
        # failure rate of episodes where it's the strongest cue (for simplicity assume any episode with cue and negative outcome)
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

def _compute_segment_stats(episodes):
    # Cross-tabs of archetype and outcome by: photo category group (memory vs utility), photo origin, platform, language, role hints, product.
    from shared.enums import MEMORY_CATEGORIES, UTILITY_CATEGORIES
    stats = []
    dimensions = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for ep in episodes:
        arch = ep["archetype_primary"]
        cat = ep["photo_category"]
        if cat in MEMORY_CATEGORIES:
            dimensions["photo_group"]["memory"][arch].append(ep)
        elif cat in UTILITY_CATEGORIES:
            dimensions["photo_group"]["utility"][arch].append(ep)
        dimensions["photo_origin"][ep["photo_origin"]][arch].append(ep)
        dimensions["platform"][ep.get("platform", "unknown")][arch].append(ep)
        dimensions["language"][ep.get("lang", "unknown")][arch].append(ep)
        dimensions["product"][ep.get("product", "unknown")][arch].append(ep)
        for role in ep.get("role_hints", []):
            dimensions["role_hints"][role][arch].append(ep)
            
    for dim_name, dim_values in dimensions.items():
        for val, archs in dim_values.items():
            for arch, eps in archs.items():
                count = len(eps)
                outcomes = Counter(e["outcome"] for e in eps)
                stats.append({
                    "dimension": dim_name,
                    "value": val,
                    "archetype": arch,
                    "episode_count": count,
                    "outcome_mix": dict(outcomes)
                })
    return stats

def _compute_hypotheses(episodes, cues_by_episode, queries_by_episode):
    from shared.enums import MEMORY_CATEGORIES, UTILITY_CATEGORIES
    hyps = {
        "H1": {"support": [], "contradict": [], "relevant": []},
        "H2": {"support": [], "contradict": [], "relevant": []},
        "H3": {"support": [], "contradict": [], "relevant": []},
        "H4": {"support": [], "contradict": [], "relevant": []},
        "H5": {"support": [], "contradict": [], "relevant": [], "dist": {}},
        "H6": {"support": [], "contradict": [], "relevant": [], "dist": {}},
        "H7": {"support": [], "contradict": [], "relevant": []},
        "H8": {"support": [], "contradict": [], "relevant": []},
    }
    for ep in episodes:
        eid = ep["episode_id"]
        cues = cues_by_episode.get(eid, [])
        c_types = {c["cue_type"] for c in cues}
        f_modes = set(ep["failure_modes"])
        w_arounds = set(ep["workarounds"])
        outcome = ep["outcome"]
        queries = queries_by_episode.get(eid, [])
        
        # H1
        h1_support = ("time_event_anchor" in c_types or "time_life_stage" in c_types) and not any(c["cue_type"] == "time_absolute" and c["precision"] == "exact" for c in cues)
        h1_contradict = any(c["cue_type"] == "time_absolute" and c["precision"] == "exact" for c in cues) and outcome == "found_easily"
        if h1_support: hyps["H1"]["support"].append(ep)
        elif h1_contradict: hyps["H1"]["contradict"].append(ep)
        if h1_support or h1_contradict: hyps["H1"]["relevant"].append(ep)
        
        # H2
        is_received = ep["photo_origin"] in ("received_messaging", "shared_album_or_partner")
        if is_received and outcome in ("gave_up", "found_with_effort"):
            hyps["H2"]["support"].append(ep)
            hyps["H2"]["relevant"].append(ep)
        elif is_received and outcome == "found_easily":
            hyps["H2"]["contradict"].append(ep)
            hyps["H2"]["relevant"].append(ep)
            
        # H3
        h3_support = "vocabulary_mismatch" in f_modes or (bool({"purpose_use", "personal_state"} & c_types) and bool({"zero_results", "wrong_results"} & f_modes))
        h3_contradict = bool({"purpose_use", "personal_state"} & c_types) and outcome == "found_easily"
        if h3_support: hyps["H3"]["support"].append(ep)
        elif h3_contradict: hyps["H3"]["contradict"].append(ep)
        if h3_support or h3_contradict: hyps["H3"]["relevant"].append(ep)
            
        # H4
        h4_support = "too_many_results" in f_modes
        h4_contradict = ep["archetype_primary"] == "needle_in_flood" and outcome == "found_easily"
        if h4_support: hyps["H4"]["support"].append(ep)
        elif h4_contradict: hyps["H4"]["contradict"].append(ep)
        if h4_support or h4_contradict: hyps["H4"]["relevant"].append(ep)
            
        # H7
        h7_support = len(queries) >= 3 and "timeline_scroll" in w_arounds
        h7_contradict = len(queries) >= 3 and outcome == "found_easily"
        if h7_support: hyps["H7"]["support"].append(ep)
        elif h7_contradict: hyps["H7"]["contradict"].append(ep)
        if h7_support or h7_contradict: hyps["H7"]["relevant"].append(ep)
            
        # H8
        text_content = (ep.get("quote_en", "") + " " + ep.get("summary_en", "")).lower()
        h8_support = ("timeline_scroll" in w_arounds and ("habitual" in text_content or "always" in text_content)) or "asked_sender_resend" in w_arounds or "none_gave_up" in w_arounds
        h8_contradict = ep.get("relevance_class") == "success_or_tip" and "always works" in text_content
        if h8_support: hyps["H8"]["support"].append(ep)
        elif h8_contradict: hyps["H8"]["contradict"].append(ep)
        if h8_support or h8_contradict: hyps["H8"]["relevant"].append(ep)
            
    # H5
    hyps["H5"]["dist"] = {"memory": {}, "utility": {}}
    for ep in episodes:
        group = "memory" if ep["photo_category"] in MEMORY_CATEGORIES else ("utility" if ep["photo_category"] in UTILITY_CATEGORIES else None)
        if group:
            for c in cues_by_episode.get(ep["episode_id"], []):
                hyps["H5"]["dist"][group][c["cue_type"]] = hyps["H5"]["dist"][group].get(c["cue_type"], 0) + 1
            for f in ep["failure_modes"]:
                hyps["H5"]["dist"][group][f] = hyps["H5"]["dist"][group].get(f, 0) + 1

    # H6
    hyps["H6"]["dist"] = {}
    for ep in episodes:
        ab = ep["photo_age_bucket"]
        if ab:
            if ab not in hyps["H6"]["dist"]: hyps["H6"]["dist"][ab] = {"total": 0, "imprecision": 0}
            hyps["H6"]["dist"][ab]["total"] += 1
            if "date_imprecision" in ep["failure_modes"]:
                hyps["H6"]["dist"][ab]["imprecision"] += 1
                
    results = []
    evidence = []
    
    titles = {
        "H1": "Relational anchoring beats dates",
        "H2": "Received photos are hardest",
        "H3": "Vocabulary mismatch",
        "H4": "Needle in a flood",
        "H5": "Utility photos are a distinct segment",
        "H6": "Time drift grows with age",
        "H7": "Refinement dead end",
        "H8": "Silent abandonment"
    }

    statements = {
        "H1": "Relational anchoring: users remember photos relative to other life events more than by dates, and search can't use event anchors.",
        "H2": "Provenance amnesia: photos received from others are the hardest to find because users remember the sender or conversation, which search doesn't index.",
        "H3": "Vocabulary mismatch: users describe photos by meaning or purpose while the index uses visual labels.",
        "H4": "Needle in a flood: for recurring subjects, recall works but ranking fails and users scroll through near-duplicates.",
        "H5": "Utility photos are a distinct segment: screenshots, receipts, documents and medicines are remembered by task and text, not visuals.",
        "H6": "Time drift grows with age: date memory gets less precise for older photos while date filters assume precision.",
        "H7": "Refinement dead end: users try a few queries, cannot narrow results, and fall back to scrolling.",
        "H8": "Silent abandonment: after repeated failures, users stop using search and rely on scrolling or asking others to resend."
    }
    
    for hid, data in hyps.items():
        support_cnt = len(data["support"])
        contra_cnt = len(data["contradict"])
        rel_cnt = len(data["relevant"])
        
        status = compute_hypothesis_status(support_cnt, contra_cnt, rel_cnt) if hid not in ("H5", "H6") else "insufficient_data"
        ev_str = compute_evidence_strength(rel_cnt) if hid not in ("H5", "H6") else "anecdotal"
        
        results.append({
            "hypothesis_id": hid,
            "title": titles[hid],
            "statement": statements[hid],
            "status": status,
            "support_count": support_cnt,
            "contradict_count": contra_cnt,
            "relevant_count": rel_cnt,
            "evidence_strength": ev_str,
            "details": json.dumps(data.get("dist", {}))
        })
        
        # top evidence
        # rank by extraction_confidence (high>medium>low) then source diversity
        for idx, ep in enumerate(sorted(data["support"], key=lambda x: (x["extraction_confidence"] == "high", x["source"]), reverse=True)[:5]):
            evidence.append({"hypothesis_id": hid, "episode_id": ep["episode_id"], "direction": "support", "rank": idx+1})
        for idx, ep in enumerate(sorted(data["contradict"], key=lambda x: (x["extraction_confidence"] == "high", x["source"]), reverse=True)[:3]):
            evidence.append({"hypothesis_id": hid, "episode_id": ep["episode_id"], "direction": "contradict", "rank": idx+1})
            
    return results, evidence


def run_analyze() -> dict:
    now = datetime.now(timezone.utc)
    
    with engine.begin() as conn:
        episode_rows = conn.execute(text("""
            SELECT e.episode_id, e.record_id, e.archetype_primary, e.archetype_secondary,
                   e.outcome, e.stakes, e.photo_category, e.photo_origin,
                   e.failure_modes, e.workarounds, e.extraction_confidence,
                   r.source, r.lang, e.summary_en, e.quote_en, e.photo_age_bucket, r.relevance_class, r.product
            FROM episodes e
            JOIN raw_records r ON e.record_id = r.record_id
        """)).fetchall()

        cue_rows = conn.execute(text(
            "SELECT episode_id, cue_type, value, precision FROM episode_cues"
        )).fetchall()

        query_rows = conn.execute(text(
            "SELECT episode_id, query_text, query_style, position FROM episode_queries ORDER BY position"
        )).fetchall()

        forgotten_rows = conn.execute(text(
            "SELECT episode_id, cue_type, evidence FROM episode_forgotten"
        )).fetchall()

        general_rows = conn.execute(text("""
            SELECT general_failure_modes
            FROM raw_records
            WHERE relevance_class = 'general_search_complaint'
              AND general_failure_modes IS NOT NULL
              AND array_length(general_failure_modes, 1) > 0
        """)).fetchall()

    episodes = []
    forgotten_by_episode = defaultdict(list)
    forgotten_list = []
    for f in forgotten_rows:
        forgotten_by_episode[f.episode_id].append(f.cue_type)
        forgotten_list.append({"episode_id": f.episode_id, "cue_type": f.cue_type})
        
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
            "photo_age_bucket": getattr(r, 'photo_age_bucket', None),
            "failure_modes": list(r.failure_modes) if r.failure_modes else [],
            "workarounds": list(r.workarounds) if r.workarounds else [],
            "extraction_confidence": r.extraction_confidence,
            "source": r.source,
            "lang": r.lang,
            "summary_en": getattr(r, 'summary_en', ""),
            "quote_en": getattr(r, 'quote_en', ""),
            "relevance_class": getattr(r, 'relevance_class', ""),
            "product": getattr(r, 'product', ""),
            "has_forgotten_cues": len(forgotten_by_episode.get(r.episode_id, [])) > 0,
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

    general_failure_modes = [list(r.general_failure_modes) if r.general_failure_modes else [] for r in general_rows]

    arch_stats = _compute_archetype_stats(episodes, cues_by_episode, queries_by_episode)
    funnel_stats = _compute_funnel_stats(episodes, cues_by_episode, queries_by_episode, general_failure_modes)
    
    cue_stats = _compute_cue_stats(episodes, cues_by_episode, forgotten_list)
    segment_stats = _compute_segment_stats(episodes)
    hyp_results, hyp_evidence = _compute_hypotheses(episodes, cues_by_episode, queries_by_episode)

    # Capability reference seed
    try:
        with open("capability_reference.yaml", "r") as yf:
            caps_data = yaml.safe_load(yf)
            if isinstance(caps_data, dict) and "cues" in caps_data:
                caps = caps_data["cues"]
                global_verified_how = caps_data.get("verified_how", "")
                global_verified_at = caps_data.get("verified_at", "")
                if global_verified_at == "2026-09":
                    global_verified_at = "2026-09-01"
            else:
                caps = {c["cue_type"]: c for c in caps_data} if isinstance(caps_data, list) else caps_data
                global_verified_how = ""
                global_verified_at = None
    except FileNotFoundError:
        caps = {}
        global_verified_how = ""
        global_verified_at = None

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM capability_reference"))
        for k, v in caps.items():
            vh = v.get("verified_how", global_verified_how)
            va = v.get("verified_at", global_verified_at)
            if not va:
                va = now
            conn.execute(text("""INSERT INTO capability_reference (cue_type, searchable, note, verified_how, verified_at)
                                 VALUES (:ct, :s, :n, :vh, :va)"""),
                         {"ct": k, "s": v.get("searchable", "no"), "n": v.get("note", ""), "vh": vh, "va": va})

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
                "archetype": s["archetype"], "episode_count": s["episode_count"], "share_of_episodes": s["share_of_episodes"],
                "outcome_distribution": json.dumps(s["outcome_distribution"]), "top_cue_types": json.dumps(s["top_cue_types"]),
                "top_failure_modes": json.dumps(s["top_failure_modes"]), "top_workarounds": json.dumps(s["top_workarounds"]),
                "source_mix": json.dumps(s["source_mix"]), "language_mix": json.dumps(s["language_mix"]), "category_mix": json.dumps(s["category_mix"]),
                "avg_severity": s["avg_severity"], "avg_stakes_weight": s["avg_stakes_weight"], "opportunity_score": s["opportunity_score"],
                "evidence_strength": s["evidence_strength"], "computed_at": now,
            })

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
                "stage": f["stage"], "episode_count": f["episode_count"], "general_complaint_count": f["general_complaint_count"],
                "gave_up_rate": f["gave_up_rate"], "avg_severity": f["avg_severity"], "evidence_strength": f["evidence_strength"],
                "details": f["details"], "computed_at": now,
            })

        conn.execute(text("DELETE FROM cue_stats"))
        for c in cue_stats:
            cap_info = caps.get(c["cue_type"], {})
            searchable = cap_info.get("searchable", "not_verified")
            gap = compute_gap_score(c["remembered_share"], searchable) if searchable != "not_verified" else None
            
            conn.execute(text("""
                INSERT INTO cue_stats (cue_type, remembered_share, precision_exact, precision_approximate, precision_vague, forgotten_count, failure_rate, gap_score, computed_at)
                VALUES (:ct, :rs, :pe, :pa, :pv, :fc, :fr, :gs, :ca)
            """), {
                "ct": c["cue_type"], "rs": c["remembered_share"], "pe": c["precision_exact"], "pa": c["precision_approximate"], "pv": c["precision_vague"],
                "fc": c["forgotten_count"], "fr": c["failure_rate"], "gs": gap, "ca": now
            })

        conn.execute(text("DELETE FROM segment_stats"))
        for ss in segment_stats:
            conn.execute(text("""
                INSERT INTO segment_stats (dimension, value, archetype, episode_count, outcome_mix)
                VALUES (:d, :v, :a, :c, :om)
            """), {
                "d": ss["dimension"], "v": ss["value"], "a": ss["archetype"], "c": ss["episode_count"], "om": json.dumps(ss["outcome_mix"])
            })

        conn.execute(text("DELETE FROM hypothesis_evidence"))
        conn.execute(text("DELETE FROM hypotheses"))
        for h in hyp_results:
            conn.execute(text("""
                INSERT INTO hypotheses (hypothesis_id, title, statement, status, support_count, contradict_count, relevant_count, evidence_strength, details, computed_at)
                VALUES (:id, :t, :s, :st, :sc, :cc, :rc, :es, :d, :ca)
            """), {
                "id": h["hypothesis_id"], "t": h["title"], "s": h["statement"], "st": h["status"], "sc": h["support_count"],
                "cc": h["contradict_count"], "rc": h["relevant_count"], "es": h["evidence_strength"], "d": h["details"], "ca": now
            })
        for he in hyp_evidence:
            conn.execute(text("""
                INSERT INTO hypothesis_evidence (hypothesis_id, episode_id, direction, rank)
                VALUES (:hid, :eid, :d, :r)
            """), {
                "hid": he["hypothesis_id"], "eid": he["episode_id"], "d": he["direction"], "r": he["rank"]
            })

    return {
        "archetypes_written": len(arch_stats),
        "funnel_stages_written": len(funnel_stats),
        "total_episodes": len(episodes),
    }

if __name__ == "__main__":
    run_analyze()
