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

@router.get("/overview")
async def get_overview():
    cached = get_cached("overview")
    if cached: return cached

    kpis_query = """
        SELECT 
            (SELECT count(*) FROM raw_records) as total_records,
            (SELECT count(*) FROM raw_records WHERE scope IN ('core', 'adjacent')) as relevant_records,
            (SELECT count(*) FROM signals) as total_signals,
            (SELECT count(*) FROM episodes) as total_episodes,
            (SELECT count(DISTINCT source) FROM raw_records) as sources_active,
            (SELECT min(created_at) FROM raw_records) as date_min,
            (SELECT max(created_at) FROM raw_records) as date_max
    """
    
    (
        kpis, 
        funnel_raw, funnel_deduped, funnel_keyword, funnel_success_tip, funnel_failed,
        source_bd, lang_bd, class_bd, prod_bd, storage, dropped_sigs,
        sig_scope_bd, sig_class_bd, sig_source_bd
    ) = await asyncio.gather(
        fetch_one(kpis_query),
        fetch_one("SELECT count(*) as c FROM raw_records"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE exclusion_reason IS NULL OR exclusion_reason NOT IN ('duplicate', 'too_short')"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE keyword_hit = true"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE relevance_class = 'success_or_tip'"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE status = 'extract_failed'"),
        execute_query("SELECT r.source, count(*) as count FROM signals s JOIN raw_records r ON s.record_id = r.record_id GROUP BY r.source"),
        execute_query("SELECT r.lang, count(*) as count FROM signals s JOIN raw_records r ON s.record_id = r.record_id GROUP BY r.lang"),
        execute_query("SELECT r.relevance_class, count(*) as count FROM signals s JOIN raw_records r ON s.record_id = r.record_id GROUP BY r.relevance_class"),
        execute_query("SELECT s.product, count(*) as count FROM signals s JOIN raw_records r ON s.record_id = r.record_id GROUP BY s.product"),
        fetch_one("SELECT pg_database_size(current_database()) as size"),
        fetch_one("SELECT count(*) as c FROM signals WHERE is_signal = false"),
        execute_query("SELECT r.scope, count(*) as count FROM signals s JOIN raw_records r ON s.record_id = r.record_id WHERE s.is_signal = true GROUP BY r.scope"),
        execute_query("SELECT r.relevance_class, count(*) as count FROM signals s JOIN raw_records r ON s.record_id = r.record_id WHERE s.is_signal = true GROUP BY r.relevance_class"),
        execute_query("SELECT r.source, count(*) as count FROM signals s JOIN raw_records r ON s.record_id = r.record_id WHERE s.is_signal = true GROUP BY r.source")
    )
    
    # Top Themes
    top_themes = await execute_query("SELECT * FROM themes ORDER BY rank_score DESC LIMIT 5")
    
    # Funnel by scope
    funnel_stats = await execute_query("SELECT * FROM funnel_stats")

    funnel = {
        "raw": funnel_raw["c"] if funnel_raw else 0,
        "deduped": funnel_deduped["c"] if funnel_deduped else 0,
        "keyword_pass": funnel_keyword["c"] if funnel_keyword else 0,
        "llm_relevant": kpis["relevant_records"] if kpis else 0,
        "extracted_signals": kpis["total_signals"] if kpis else 0,
        "extracted_episodes": kpis["total_episodes"] if kpis else 0,
        "success_tip": funnel_success_tip["c"] if funnel_success_tip else 0,
        "failed_extractions": funnel_failed["c"] if funnel_failed else 0,
        "dropped_at_signals": dropped_sigs["c"] if dropped_sigs else 0,
    }

    # Don't overwrite total_episodes with total_signals
    # The kpis query already returns total_episodes natively now.

    # Sufficiency data for the frontend
    sufficiency_rows = await execute_query(
        "SELECT evidence_strength, count(*) as count FROM hypotheses GROUP BY evidence_strength"
    )
    
    result = {
        "kpis": kpis,
        "funnel": funnel,
        "breakdowns": {
            "source": source_bd,
            "language": lang_bd,
            "relevance": class_bd,
            "product": prod_bd,
        },
        "signal_breakdowns": {
            "scope": sig_scope_bd,
            "relevance_class": sig_class_bd,
            "source": sig_source_bd
        },
        "sufficiency": sufficiency_rows or [],
        "top_themes": top_themes,
        "funnel_stats": funnel_stats,
        "pipeline_health": {
            "storage_bytes": storage["size"] if storage else 0
        }
    }
    set_cached("overview", result)
    return result


@router.get("/funnel")
async def get_funnel():
    try:
        return await execute_query("SELECT * FROM funnel_stats")
    except Exception:
        return []

@router.get("/themes")
async def list_themes(scope: Optional[str] = None):
    cached = get_cached(f"themes_{scope}")
    if cached: return cached
    
    query = "SELECT * FROM themes"
    params = {}
    if scope:
        query += " WHERE scope = :scope"
        params["scope"] = scope
    query += " ORDER BY rank_score DESC"
    
    res = await execute_query(query, params)
    set_cached(f"themes_{scope}", res)
    return res

@router.get("/themes/{id}")
async def get_theme(id: str):
    cached = get_cached(f"theme_{id}")
    if cached: return cached
    
    theme = await fetch_one("SELECT * FROM themes WHERE id = :id", {"id": id})
    if not theme:
        return {"error": "Not found"}
        
    res = {"theme": theme}
    set_cached(f"theme_{id}", res)
    return res

@router.get("/hypotheses")
async def list_hypotheses():
    cached = get_cached("hypotheses")
    if cached: return cached
    query = """
        SELECT h.*, t.scope
        FROM hypotheses h
        LEFT JOIN themes t ON h.theme_id = t.id
        WHERE h.origin = 'data_derived'
        ORDER BY h.rank DESC
    """
    res = await execute_query(query)
    set_cached("hypotheses", res)
    return res

@router.get("/hypotheses/{id}")
async def get_hypothesis(id: str):
    cached = get_cached(f"hypotheses_{id}")
    if cached: return cached
    
    hyp, lit_sources = await asyncio.gather(
        fetch_one("SELECT * FROM hypotheses WHERE hypothesis_id = :id", {"id": id}),
        execute_query("""
            SELECT * FROM literature_sources
            WHERE :id = ANY(tags)
        """, {"id": id})
    )
    
    if not hyp:
        return {"error": "Not found"}
        
    res = {
        "hypothesis": hyp,
        "research_evidence": lit_sources
    }
    set_cached(f"hypotheses_{id}", res)
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

@router.get("/signals")
async def list_signals(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    scope: Optional[str] = None,
    relevance_class: Optional[str] = None,
    theme: Optional[str] = None,
    source: Optional[str] = None,
    product: Optional[str] = None,
    funnel_stage: Optional[str] = None,
    outcome: Optional[str] = None
):
    where = ["s.is_signal = TRUE"]
    params = {}
    
    if scope:
        where.append("r.scope = :scope")
        params["scope"] = scope
    if relevance_class:
        where.append("r.relevance_class = :relevance_class")
        params["relevance_class"] = relevance_class
    if theme:
        where.append("EXISTS (SELECT 1 FROM signal_reasons sr WHERE sr.signal_id = s.signal_id AND sr.theme_id = :theme)")
        params["theme"] = theme
    if source:
        where.append("r.source = :source")
        params["source"] = source
    if product:
        where.append("s.product = :product")
        params["product"] = product
    if outcome:
        where.append("s.outcome = :outcome")
        params["outcome"] = outcome
    if funnel_stage:
        where.append("EXISTS (SELECT 1 FROM signal_reasons sr WHERE sr.signal_id = s.signal_id AND sr.funnel_stage = :funnel_stage)")
        params["funnel_stage"] = funnel_stage
        
    where_clause = "WHERE " + " AND ".join(where)
    
    count_q = f"SELECT count(*) as c FROM signals s JOIN raw_records r ON s.record_id = r.record_id {where_clause}"
    
    data_q = f"""
        SELECT s.*, r.source, r.lang, r.created_at, r.url, r.scope, r.relevance_class, t.name AS theme_name
        FROM signals s
        JOIN raw_records r ON s.record_id = r.record_id
        LEFT JOIN (SELECT signal_id, MAX(theme_id) as theme_id FROM signal_reasons GROUP BY signal_id) sr ON sr.signal_id = s.signal_id
        LEFT JOIN themes t ON t.id = sr.theme_id
        {where_clause}
        ORDER BY r.created_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    params_data = params.copy()
    params_data["limit"] = per_page
    params_data["offset"] = (page - 1) * per_page
    
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

@router.get("/episodes")
async def list_episodes(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    count_q = "SELECT count(*) as c FROM episodes e"
    data_q = """
        SELECT e.*, r.source, r.lang, r.created_at, r.url
        FROM episodes e
        JOIN raw_records r ON e.record_id = r.record_id
        ORDER BY r.created_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    
    total_res, data = await asyncio.gather(
        fetch_one(count_q),
        execute_query(data_q, {"limit": per_page, "offset": (page - 1) * per_page})
    )
    
    return {
        "items": data,
        "total": total_res["c"] if total_res else 0,
        "page": page,
        "per_page": per_page
    }

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
    
    funnel_raw, funnel_deduped, funnel_keyword, funnel_rel, funnel_sigs, example = await asyncio.gather(
        fetch_one("SELECT count(*) as c FROM raw_records"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE exclusion_reason IS NULL OR exclusion_reason NOT IN ('duplicate', 'too_short')"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE keyword_hit = true"),
        fetch_one("SELECT count(*) as c FROM raw_records WHERE scope IN ('core', 'adjacent')"),
        fetch_one("SELECT count(*) as c FROM signals"),
        fetch_one("""
            SELECT s.*, r.lang, r.url 
            FROM signals s 
            JOIN raw_records r ON s.record_id = r.record_id 
            WHERE r.lang != 'en' LIMIT 1
        """)
    )
    
    if not example:
        example = await fetch_one("SELECT s.*, r.lang, r.url FROM signals s JOIN raw_records r ON s.record_id = r.record_id LIMIT 1")
    
    res = {
        "funnel": {
            "raw": funnel_raw["c"] if funnel_raw else 0,
            "deduped": funnel_deduped["c"] if funnel_deduped else 0,
            "keyword_pass": funnel_keyword["c"] if funnel_keyword else 0,
            "llm_relevant": funnel_rel["c"] if funnel_rel else 0,
            "extracted_signals": funnel_sigs["c"] if funnel_sigs else 0,
        },
        "example_signal": example,
        "config": {
            "time_window": "24 months",
            "models": ["gemini-3.5-flash-lite", "gemini-3.8-flash", "BAAI/bge-small-en-v1.5"]
        }
    }
    set_cached("how-it-works", res)
    return res

@router.get("/literature")
async def list_literature():
    cached = get_cached("literature")
    if cached: return cached
    res = await execute_query("SELECT * FROM literature_sources ORDER BY id")
    set_cached("literature", res)
    return res

@router.get("/segments")
async def get_segments(dimension: str):
    allowed = ["source", "product", "class", "language", "photo_group", "photo_origin", "platform"]
    if dimension not in allowed:
        return []
        
    cached = get_cached(f"segments_{dimension}")
    if cached: return cached
    
    data = await execute_query("SELECT * FROM segment_stats WHERE dimension = :d", {"d": dimension})
    set_cached(f"segments_{dimension}", data)
    return data

@router.get("/handoff")
async def get_handoff():
    cached = get_cached("handoff")
    if cached: return cached
    
    hyps = await execute_query("""
        SELECT hypothesis_id, title, statement, research_question 
        FROM hypotheses 
        WHERE origin = 'data_derived' 
        ORDER BY rank DESC
    """)
    
    # Backward compatibility for frontend build
    d1 = await execute_query("SELECT hypothesis_id, title, status FROM hypotheses WHERE evidence_strength IN ('directional', 'strong')")
    
    try:
        drafts = await execute_query("SELECT * FROM research_handoff")
    except Exception:
        drafts = []
        
    res = {
        "hypotheses": hyps or [],
        "decisions": {
            "D1": d1 or [],
            "D2": "See top segments in segment explorer",
            "D3": "Not determined",
            "D4": "Not prioritized for D4"
        },
        "drafts": drafts or []
    }
    set_cached("handoff", res)
    return res


@router.post("/chat")
async def chat(request: Request):
    """POST /api/v1/chat — RAG chat endpoint (FR-100 – FR-108)."""
    from backend.services.rate_limiter import chat_rate_limiter
    from backend.services.chat import handle_chat
    from backend.main import embedding_model

    # Rate limiting (FR-106)
    client_ip = request.client.host if request.client else "unknown"
    rate_result = chat_rate_limiter.check(client_ip)
    if not rate_result.allowed:
        return Response(
            content=json.dumps({
                "error": "Rate limit exceeded",
                "retry_after_seconds": rate_result.retry_after_seconds,
            }),
            status_code=429,
            media_type="application/json",
        )

    body = await request.json()
    question = body.get("question", "").strip()
    if not question:
        return Response(
            content=json.dumps({"error": "Question is required"}),
            status_code=400,
            media_type="application/json",
        )

    filters = body.get("filters")

    try:
        result = await handle_chat(
            question=question,
            embedding_model=embedding_model,
            filters=filters,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response(
            content=json.dumps({"error": f"Chat failed: {str(e)}"}),
            status_code=500,
            media_type="application/json",
        )
