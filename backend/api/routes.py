from fastapi import APIRouter, Query, Request, Response
from typing import Optional, List, Any
import json
import time
import asyncio
from backend.services.data import execute_query, fetch_one
import csv
import io

router = APIRouter()

_cache = {}
CACHE_TTL = 600

def get_cached(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry['time'] < CACHE_TTL:
        return entry['data']
    return None

def set_cached(key: str, data: Any):
    _cache[key] = {'data': data, 'time': time.time()}

def clear_cache():
    _cache.clear()

@router.post("/cache/clear")
async def clear_cache_endpoint():
    clear_cache()
    return {"status": "cleared"}

def build_filter_where(source, product, lang, from_date, to_date, prefix="e"):
    conditions = []
    params = {}
    if source:
        conditions.append(f"{prefix}.source = :source")
        params["source"] = source
    if product:
        conditions.append(f"{prefix}.product = :product")
        params["product"] = product
    if lang:
        conditions.append(f"{prefix}.lang = :lang")
        params["lang"] = lang
    if from_date:
        conditions.append(f"{prefix}.created_at >= :from_date")
        params["from_date"] = from_date
    if to_date:
        conditions.append(f"{prefix}.created_at <= :to_date")
        params["to_date"] = to_date
    return (" AND ".join(conditions), params) if conditions else ("", {})

@router.get("/overview")
async def get_overview():
    cached = get_cached("overview")
    if cached: return cached

    kpis_query = """
        SELECT 
            (SELECT count(*) FROM raw_records) as total_records,
            (SELECT count(*) FROM raw_records WHERE relevance_class IN ('specific_episode', 'success_or_tip')) as relevant_records,
            (SELECT count(*) FROM episodes) as total_episodes,
            (SELECT count(*) FROM raw_records WHERE relevance_class = 'success_or_tip') as success_tip_records,
            (SELECT count(DISTINCT source) FROM raw_records) as sources_active,
            (SELECT min(created_at) FROM raw_records) as date_min,
            (SELECT max(created_at) FROM raw_records) as date_max
    """
    
    (
        kpis, 
        funnel_raw, funnel_deduped, funnel_keyword,
        source_bd, lang_bd, rel_bd, prod_bd, suff, failed, storage
    ) = await asyncio.gather(
        fetch_one(kpis_query),
        fetch_one("SELECT count(*) as c FROM raw_records"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE status != 'raw'"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE keyword_hit = true"),
        execute_query("SELECT source, count(*) as count FROM raw_records GROUP BY source"),
        execute_query("SELECT lang, count(*) as count FROM raw_records GROUP BY lang"),
        execute_query("SELECT relevance_class, count(*) as count FROM raw_records GROUP BY relevance_class"),
        execute_query("SELECT product, count(*) as count FROM raw_records GROUP BY product"),
        execute_query("SELECT evidence_strength, count(*) as count FROM hypotheses GROUP BY evidence_strength"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE status = 'extract_failed'"),
        fetch_one("SELECT pg_database_size(current_database()) as size")
    )
    
    funnel = {
        "raw": funnel_raw["c"] if funnel_raw else 0,
        "deduped": funnel_deduped["c"] if funnel_deduped else 0,
        "keyword_pass": funnel_keyword["c"] if funnel_keyword else 0,
        "llm_relevant": kpis["relevant_records"] if kpis else 0,
        "extracted_episodes": kpis["total_episodes"] if kpis else 0,
    }
    
    result = {
        "kpis": kpis,
        "funnel": funnel,
        "breakdowns": {
            "source": source_bd,
            "language": lang_bd,
            "relevance": rel_bd,
            "product": prod_bd,
        },
        "sufficiency": suff,
        "pipeline_health": {
            "failed_records": failed["c"] if failed else 0,
            "storage_bytes": storage["size"] if storage else 0
        }
    }
    set_cached("overview", result)
    return result

@router.get("/hypotheses")
async def list_hypotheses():
    cached = get_cached("hypotheses")
    if cached: return cached
    res = await execute_query("SELECT * FROM hypotheses ORDER BY hypothesis_id")
    set_cached("hypotheses", res)
    return res

@router.get("/hypotheses/{id}")
async def get_hypothesis(id: str):
    cached = get_cached(f"hypotheses_{id}")
    if cached: return cached
    
    hyp, support_eps, contradict_eps = await asyncio.gather(
        fetch_one("SELECT * FROM hypotheses WHERE hypothesis_id = :id", {"id": id}),
        execute_query("""
            SELECT e.*, he.rank 
            FROM hypothesis_evidence he
            JOIN episodes e ON he.episode_id = e.episode_id
            WHERE he.hypothesis_id = :id AND he.direction = 'support'
            ORDER BY he.rank
        """, {"id": id}),
        execute_query("""
            SELECT e.*, he.rank 
            FROM hypothesis_evidence he
            JOIN episodes e ON he.episode_id = e.episode_id
            WHERE he.hypothesis_id = :id AND he.direction = 'contradict'
            ORDER BY he.rank
        """, {"id": id})
    )
    
    if not hyp:
        return {"error": "Not found"}
        
    res = {
        "hypothesis": hyp,
        "support_evidence": support_eps,
        "contradict_evidence": contradict_eps
    }
    set_cached(f"hypotheses_{id}", res)
    return res

@router.get("/emergent-labels")
async def list_emergent_labels():
    cached = get_cached("emergent-labels")
    if cached: return cached
    res = await execute_query("SELECT * FROM emergent_labels ORDER BY episode_count DESC")
    set_cached("emergent-labels", res)
    return res

@router.get("/gap-matrix")
async def get_gap_matrix():
    cached = get_cached("gap-matrix")
    if cached: return cached
    query = """
        SELECT cs.*, cr.searchable, cr.note, cr.verified_how
        FROM cue_stats cs
        LEFT JOIN capability_reference cr ON cs.cue_type = cr.cue_type
        ORDER BY cs.gap_score DESC NULLS LAST
    """
    res = await execute_query(query)
    set_cached("gap-matrix", res)
    return res

@router.get("/archetypes")
async def list_archetypes():
    cached = get_cached("archetypes")
    if cached: return cached
    res = await execute_query("SELECT * FROM archetype_stats ORDER BY opportunity_score DESC")
    set_cached("archetypes", res)
    return res

@router.get("/archetypes/compare")
async def compare_archetypes(a: str, b: str):
    cached = get_cached(f"compare_{a}_{b}")
    if cached: return cached
    
    arch_a, arch_b, quotes_a, quotes_b = await asyncio.gather(
        fetch_one("SELECT * FROM archetype_stats WHERE archetype = :a", {"a": a}),
        fetch_one("SELECT * FROM archetype_stats WHERE archetype = :b", {"b": b}),
        execute_query("SELECT quote_en, quote_original, source, url FROM episodes e JOIN raw_records r ON e.record_id = r.record_id WHERE e.archetype_primary = :a LIMIT 3", {"a": a}),
        execute_query("SELECT quote_en, quote_original, source, url FROM episodes e JOIN raw_records r ON e.record_id = r.record_id WHERE e.archetype_primary = :b LIMIT 3", {"b": b})
    )
    
    res = {
        "a": {"stats": arch_a, "quotes": quotes_a},
        "b": {"stats": arch_b, "quotes": quotes_b}
    }
    set_cached(f"compare_{a}_{b}", res)
    return res

@router.get("/episodes")
async def list_episodes(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    archetype: Optional[str] = None,
    category: Optional[str] = None,
    origin: Optional[str] = None,
    outcome: Optional[str] = None,
    stakes: Optional[str] = None,
    confidence: Optional[str] = None,
    search: Optional[str] = None
):
    where = []
    params = {}
    
    if archetype:
        where.append("e.archetype_primary = :archetype")
        params["archetype"] = archetype
    if category:
        where.append("e.photo_category = :category")
        params["category"] = category
    if origin:
        where.append("e.photo_origin = :origin")
        params["origin"] = origin
    if outcome:
        where.append("e.outcome = :outcome")
        params["outcome"] = outcome
    if stakes:
        where.append("e.stakes = :stakes")
        params["stakes"] = stakes
    if confidence:
        where.append("e.extraction_confidence = :confidence")
        params["confidence"] = confidence
    if search:
        where.append("e.summary_en ILIKE :search")
        params["search"] = f"%{search}%"
        
    where_clause = "WHERE " + " AND ".join(where) if where else ""
    
    count_q = f"SELECT count(*) as c FROM episodes e {where_clause}"
    
    data_q = f"""
        SELECT e.*, r.source, r.lang, r.created_at, r.url
        FROM episodes e
        JOIN raw_records r ON e.record_id = r.record_id
        {where_clause}
        ORDER BY r.created_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    params_data = params.copy()
    params_data["limit"] = per_page
    params_data["offset"] = (page - 1) * per_page
    
    # We do NOT cache episodes queries according to user requirements, OR cache per query
    # The requirement: "Keep /episodes filters uncached or cached per query."
    # We'll leave it uncached as we use gather for concurrent execution.
    total_res, data = await asyncio.gather(
        fetch_one(count_q, params),
        execute_query(data_q, params_data)
    )
    
    return {
        "items": data,
        "total": total_res["c"] if total_res else 0,
        "page": page,
        "per_page": per_page
    }

@router.get("/episodes/export")
async def export_episodes():
    data = await execute_query("""
        SELECT e.episode_id, e.archetype_primary, e.summary_en, e.quote_en, e.outcome, r.source, r.url
        FROM episodes e
        JOIN raw_records r ON e.record_id = r.record_id
    """)
    if not data:
        return Response("No data", media_type="text/plain")
        
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    for row in data:
        writer.writerow(row)
        
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=episodes.csv"})

@router.get("/episodes/{id}")
async def get_episode(id: str):
    ep, cues, forgotten, queries = await asyncio.gather(
        fetch_one("""
            SELECT e.*, r.source, r.lang, r.created_at, r.url 
            FROM episodes e 
            JOIN raw_records r ON e.record_id = r.record_id
            WHERE e.episode_id = :id
        """, {"id": id}),
        execute_query("SELECT * FROM episode_cues WHERE episode_id = :id", {"id": id}),
        execute_query("SELECT * FROM episode_forgotten WHERE episode_id = :id", {"id": id}),
        execute_query("SELECT * FROM episode_queries WHERE episode_id = :id ORDER BY position", {"id": id})
    )
    if not ep:
        return {"error": "Not found"}
        
    ep["cues"] = cues
    ep["forgotten"] = forgotten
    ep["queries"] = queries
    return ep

@router.get("/how-it-works")
async def get_how_it_works():
    cached = get_cached("how-it-works")
    if cached: return cached
    
    funnel_raw, funnel_deduped, funnel_keyword, funnel_rel, funnel_eps, example, eval_results = await asyncio.gather(
        fetch_one("SELECT count(*) as c FROM raw_records"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE status != 'raw'"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE keyword_hit = true"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE relevance_class IN ('specific_episode', 'success_or_tip')"),
        fetch_one("SELECT count(*) as c FROM episodes"),
        fetch_one("""
            SELECT e.*, r.lang, r.url 
            FROM episodes e 
            JOIN raw_records r ON e.record_id = r.record_id 
            WHERE r.lang != 'en' LIMIT 1
        """),
        execute_query("SELECT * FROM eval_results ORDER BY run_at DESC LIMIT 1")
    )
    
    if not example:
        example = await fetch_one("SELECT e.*, r.lang, r.url FROM episodes e JOIN raw_records r ON e.record_id = r.record_id LIMIT 1")
    
    res = {
        "funnel": {
            "raw": funnel_raw["c"] if funnel_raw else 0,
            "deduped": funnel_deduped["c"] if funnel_deduped else 0,
            "keyword_pass": funnel_keyword["c"] if funnel_keyword else 0,
            "llm_relevant": funnel_rel["c"] if funnel_rel else 0,
            "extracted_episodes": funnel_eps["c"] if funnel_eps else 0,
        },
        "example_episode": example,
        "eval_results": eval_results[0] if eval_results else None,
        "config": {
            "time_window": "24 months",
            "models": ["gemini-3.5-flash-lite", "gemini-3.8-flash", "BAAI/bge-small-en-v1.5"]
        }
    }
    set_cached("how-it-works", res)
    return res

@router.get("/segments")
async def get_segments(dimension: str):
    allowed = ["photo_category", "photo_origin", "platform", "lang", "role_hints", "product"]
    if dimension not in allowed:
        return {"error": "Invalid dimension"}
        
    cached = get_cached(f"segments_{dimension}")
    if cached: return cached
    
    data = await execute_query("SELECT * FROM segment_stats WHERE dimension = :d", {"d": dimension})
    set_cached(f"segments_{dimension}", data)
    return data

@router.get("/handoff")
async def get_handoff():
    cached = get_cached("handoff")
    if cached: return cached
    
    drafts, d1, d3 = await asyncio.gather(
        execute_query("SELECT * FROM research_handoff"),
        execute_query("SELECT hypothesis_id, title, status FROM hypotheses WHERE evidence_strength IN ('directional', 'strong')"),
        fetch_one("SELECT archetype, opportunity_score FROM archetype_stats ORDER BY opportunity_score DESC LIMIT 1")
    )
    
    res = {
        "decisions": {
            "D1": d1,
            "D2": "See top segments in segment explorer",
            "D3": d3["archetype"] if d3 else "Unknown",
            "D4": "Hypotheses contradicted by data"
        },
        "drafts": drafts
    }
    set_cached("handoff", res)
    return res

@router.get("/funnel")
async def get_funnel_stats():
    cached = get_cached("funnel")
    if cached: return cached
    res = await execute_query("SELECT * FROM funnel_stats")
    set_cached("funnel", res)
    return res
