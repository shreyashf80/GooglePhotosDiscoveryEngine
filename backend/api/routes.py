from fastapi import APIRouter, Query, Request, Response
from typing import Optional, List
import json
from backend.services.data import execute_query, fetch_one
import csv
import io

router = APIRouter()

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
    # KPIs
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
    kpis = await fetch_one(kpis_query)
    
    # Funnel
    funnel = {
        "raw": (await fetch_one("SELECT count(*) as c FROM raw_records"))["c"],
        "deduped": (await fetch_one("SELECT count(*) as c FROM raw_records WHERE status != 'raw'"))["c"],
        "keyword_pass": (await fetch_one("SELECT count(*) as c FROM raw_records WHERE keyword_hit = true"))["c"],
        "llm_relevant": kpis["relevant_records"],
        "extracted_episodes": kpis["total_episodes"],
    }
    
    # Breakdowns
    source_bd = await execute_query("SELECT source, count(*) as count FROM raw_records GROUP BY source")
    lang_bd = await execute_query("SELECT lang, count(*) as count FROM raw_records GROUP BY lang")
    rel_bd = await execute_query("SELECT relevance_class, count(*) as count FROM raw_records GROUP BY relevance_class")
    prod_bd = await execute_query("SELECT product, count(*) as count FROM raw_records GROUP BY product")
    
    # Sufficiency
    suff = await execute_query("SELECT evidence_strength, count(*) as count FROM hypotheses GROUP BY evidence_strength")
    
    # Pipeline health
    failed = await fetch_one("SELECT count(*) as c FROM raw_records WHERE status = 'extract_failed'")
    storage = await fetch_one("SELECT pg_database_size(current_database()) as size")
    
    return {
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
            "failed_records": failed["c"],
            "storage_bytes": storage["size"]
        }
    }

@router.get("/hypotheses")
async def list_hypotheses():
    return await execute_query("SELECT * FROM hypotheses ORDER BY hypothesis_id")

@router.get("/hypotheses/{id}")
async def get_hypothesis(id: str):
    hyp = await fetch_one("SELECT * FROM hypotheses WHERE hypothesis_id = :id", {"id": id})
    if not hyp:
        return {"error": "Not found"}
        
    support_eps = await execute_query("""
        SELECT e.*, he.rank 
        FROM hypothesis_evidence he
        JOIN episodes e ON he.episode_id = e.episode_id
        WHERE he.hypothesis_id = :id AND he.direction = 'support'
        ORDER BY he.rank
    """, {"id": id})
    
    contradict_eps = await execute_query("""
        SELECT e.*, he.rank 
        FROM hypothesis_evidence he
        JOIN episodes e ON he.episode_id = e.episode_id
        WHERE he.hypothesis_id = :id AND he.direction = 'contradict'
        ORDER BY he.rank
    """, {"id": id})
    
    return {
        "hypothesis": hyp,
        "support_evidence": support_eps,
        "contradict_evidence": contradict_eps
    }

@router.get("/emergent-labels")
async def list_emergent_labels():
    return await execute_query("SELECT * FROM emergent_labels ORDER BY episode_count DESC")

@router.get("/gap-matrix")
async def get_gap_matrix():
    query = """
        SELECT cs.*, cr.searchable, cr.note, cr.verified_how
        FROM cue_stats cs
        LEFT JOIN capability_reference cr ON cs.cue_type = cr.cue_type
        ORDER BY cs.gap_score DESC NULLS LAST
    """
    return await execute_query(query)

@router.get("/archetypes")
async def list_archetypes():
    return await execute_query("SELECT * FROM archetype_stats ORDER BY opportunity_score DESC")

@router.get("/archetypes/compare")
async def compare_archetypes(a: str, b: str):
    arch_a = await fetch_one("SELECT * FROM archetype_stats WHERE archetype = :a", {"a": a})
    arch_b = await fetch_one("SELECT * FROM archetype_stats WHERE archetype = :b", {"b": b})
    
    quotes_a = await execute_query("SELECT quote_en, quote_original, source, url FROM episodes e JOIN raw_records r ON e.record_id = r.record_id WHERE e.archetype_primary = :a LIMIT 3", {"a": a})
    quotes_b = await execute_query("SELECT quote_en, quote_original, source, url FROM episodes e JOIN raw_records r ON e.record_id = r.record_id WHERE e.archetype_primary = :b LIMIT 3", {"b": b})
    
    return {
        "a": {"stats": arch_a, "quotes": quotes_a},
        "b": {"stats": arch_b, "quotes": quotes_b}
    }

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
    total = (await fetch_one(count_q, params))["c"]
    
    data_q = f"""
        SELECT e.*, r.source, r.lang, r.created_at, r.url
        FROM episodes e
        JOIN raw_records r ON e.record_id = r.record_id
        {where_clause}
        ORDER BY r.created_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page
    
    data = await execute_query(data_q, params)
    
    return {
        "items": data,
        "total": total,
        "page": page,
        "per_page": per_page
    }

@router.get("/episodes/export")
async def export_episodes():
    # Basic CSV export (ignoring filters for simplicity, P1)
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
    ep = await fetch_one("""
        SELECT e.*, r.source, r.lang, r.created_at, r.url 
        FROM episodes e 
        JOIN raw_records r ON e.record_id = r.record_id
        WHERE e.episode_id = :id
    """, {"id": id})
    if not ep:
        return {"error": "Not found"}
        
    cues = await execute_query("SELECT * FROM episode_cues WHERE episode_id = :id", {"id": id})
    forgotten = await execute_query("SELECT * FROM episode_forgotten WHERE episode_id = :id", {"id": id})
    queries = await execute_query("SELECT * FROM episode_queries WHERE episode_id = :id ORDER BY position", {"id": id})
    
    ep["cues"] = cues
    ep["forgotten"] = forgotten
    ep["queries"] = queries
    return ep

@router.get("/how-it-works")
async def get_how_it_works():
    funnel = {
        "raw": (await fetch_one("SELECT count(*) as c FROM raw_records"))["c"],
        "deduped": (await fetch_one("SELECT count(*) as c FROM raw_records WHERE status != 'raw'"))["c"],
        "keyword_pass": (await fetch_one("SELECT count(*) as c FROM raw_records WHERE keyword_hit = true"))["c"],
        "llm_relevant": (await fetch_one("SELECT count(*) as c FROM raw_records WHERE relevance_class IN ('specific_episode', 'success_or_tip')"))["c"],
        "extracted_episodes": (await fetch_one("SELECT count(*) as c FROM episodes"))["c"],
    }
    
    # Try to find a non-English example
    example = await fetch_one("""
        SELECT e.*, r.lang, r.url 
        FROM episodes e 
        JOIN raw_records r ON e.record_id = r.record_id 
        WHERE r.lang != 'en' LIMIT 1
    """)
    if not example:
        example = await fetch_one("SELECT e.*, r.lang, r.url FROM episodes e JOIN raw_records r ON e.record_id = r.record_id LIMIT 1")
        
    eval_results = await execute_query("SELECT * FROM eval_results ORDER BY run_at DESC LIMIT 1")
    
    return {
        "funnel": funnel,
        "example_episode": example,
        "eval_results": eval_results[0] if eval_results else None,
        "config": {
            "time_window": "24 months",
            "models": ["gemini-3.5-flash-lite", "gemini-3.8-flash", "BAAI/bge-small-en-v1.5"]
        }
    }

@router.get("/segments")
async def get_segments(dimension: str):
    # Allowed dimensions: photo_category, photo_origin, platform, lang, role_hints, product
    allowed = ["photo_category", "photo_origin", "platform", "lang", "role_hints", "product"]
    if dimension not in allowed:
        return {"error": "Invalid dimension"}
        
    data = await execute_query("SELECT * FROM segment_stats WHERE dimension = :d", {"d": dimension})
    return data

@router.get("/handoff")
async def get_handoff():
    drafts = await execute_query("SELECT * FROM research_handoff")
    
    # Simple D1-D4 summary (D1: hypotheses with directional/strong evidence)
    d1 = await execute_query("SELECT hypothesis_id, title, status FROM hypotheses WHERE evidence_strength IN ('directional', 'strong')")
    d3 = await fetch_one("SELECT archetype, opportunity_score FROM archetype_stats ORDER BY opportunity_score DESC LIMIT 1")
    
    return {
        "decisions": {
            "D1": d1,
            "D2": "See top segments in segment explorer",
            "D3": d3["archetype"] if d3 else "Unknown",
            "D4": "Hypotheses contradicted by data"
        },
        "drafts": drafts
    }

@router.get("/funnel")
async def get_funnel_stats():
    # FR-88 funnel stats
    return await execute_query("SELECT * FROM funnel_stats")

