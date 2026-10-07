"""
Chat service — RAG pipeline for "Ask the corpus" feature.

Flow (FR-100):
  1. Gemini rewrites user question into a concise English search query
  2. Embed the rewritten query with BGE-small
  3. Retrieve top 12 episodes + top 4 literature chunks by cosine similarity
  4. Inject precomputed stats snapshot for counting questions (FR-103)
  5. Gemini answers using only the provided context with numbered citations
  6. Validate all citation IDs exist; strip invalid ones (FR-101)

References: FR-100 – FR-104, FR-106
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from google import genai
from google.genai import types

from backend.services.data import execute_query, fetch_one

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
GEMINI_CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
GEMINI_API_KEYS = [k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()]

EPISODE_SIMILARITY_THRESHOLD = 0.35
LITERATURE_SIMILARITY_THRESHOLD = 0.30
MIN_EPISODES_FOR_SUFFICIENT = 3

CACHE_TTL_DAYS = 7


# ── KeyPool (lightweight async-compatible version) ──────────────────────────
class _ChatKeyPool:
    """Simple round-robin key selection for the chat service."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = keys
        self._index = 0

    def acquire(self) -> str:
        if not self._keys:
            raise RuntimeError("No GEMINI_API_KEYS configured")
        key = self._keys[self._index % len(self._keys)]
        self._index += 1
        return key

_key_pool = _ChatKeyPool(GEMINI_API_KEYS)


# ── Helper: call Gemini ─────────────────────────────────────────────────────
def _call_gemini(
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.2,
    response_mime_type: str | None = None,
    max_retries: int = 2,
) -> str:
    """Make a Gemini API call with key rotation and retry logic."""
    import time as _time

    last_error = None
    for attempt in range(max_retries):
        key = _key_pool.acquire()
        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000, retry_options=types.HttpRetryOptions(attempts=1)))

        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if response_mime_type:
            config_kwargs["response_mime_type"] = response_mime_type

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            **config_kwargs,
        )

        try:
            response = client.models.generate_content(
                model=GEMINI_CHAT_MODEL,
                contents=prompt,
                config=config,
            )

            text = response.text
            if not text:
                raise RuntimeError("Gemini returned empty response")
            return text
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            is_transient = any(s in error_str for s in ["503", "429", "unavailable", "rate", "quota", "overloaded", "high demand"])
            if is_transient and attempt < max_retries - 1:
                wait = min(2 ** attempt, 15)
                logger.warning("Gemini transient error (attempt %d/%d): %s. Retrying in %ds...", attempt + 1, max_retries, type(e).__name__, wait)
                _time.sleep(wait)
                continue
            raise

    raise RuntimeError(f"Gemini API failed after {max_retries} retries: {last_error}")


# ── Step 1: Rewrite question ────────────────────────────────────────────────
def rewrite_query(question: str) -> str:
    """Use Gemini to rewrite the user question into a concise English search query."""
    system = (
        "You are a search query rewriter. Rewrite the user's question into a concise "
        "English search query suitable for semantic search over a corpus of user episodes "
        "about photo retrieval failures in Google Photos. "
        "Return ONLY the rewritten query, nothing else. Keep it under 15 words."
    )
    result = _call_gemini(question, system_instruction=system, temperature=0.1)
    return result.strip().strip('"').strip("'")


# ── Step 2: Embed the query ─────────────────────────────────────────────────
def embed_query(text: str, embedding_model: Any) -> list[float]:
    """Embed text using the loaded BGE-small model."""
    embeddings = list(embedding_model.embed([text]))
    return embeddings[0].tolist()


# ── Step 3: Retrieve episodes and literature ─────────────────────────────────
async def retrieve_episodes(
    query_embedding: list[float],
    limit: int = 12,
    filters: dict | None = None,
) -> list[dict]:
    """Retrieve top signals by cosine similarity, excluding duplicates and out-of-scope."""
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    where_clauses = [
        "s.embedding IS NOT NULL",
        "s.is_signal = true",
    ]
    params: dict[str, Any] = {"emb": embedding_str, "lim": limit}

    if filters:
        if filters.get("source"):
            where_clauses.append("r.source = :source")
            params["source"] = filters["source"]
        if filters.get("product"):
            where_clauses.append("s.product = :product")
            params["product"] = filters["product"]
        if filters.get("scope"):
            where_clauses.append("r.scope = :scope")
            params["scope"] = filters["scope"]
        if filters.get("theme"):
            where_clauses.append("EXISTS (SELECT 1 FROM signal_reasons sr JOIN themes t ON sr.theme_id = t.id WHERE sr.signal_id = s.signal_id AND t.name = :theme)")
            params["theme"] = filters["theme"]
        if filters.get("theme_id"):
            where_clauses.append("EXISTS (SELECT 1 FROM signal_reasons sr WHERE sr.signal_id = s.signal_id AND sr.theme_id = :theme_id)")
            params["theme_id"] = filters["theme_id"]
        if filters.get("lang"):
            where_clauses.append("r.lang = :lang")
            params["lang"] = filters["lang"]

    where_sql = " AND ".join(where_clauses)

    query = f"""
        SELECT
            s.signal_id,
            s.summary_en as summary,
            s.quote_en as quote,
            s.quote_original,
            (SELECT t.name FROM themes t JOIN signal_reasons sr ON sr.theme_id = t.id WHERE sr.signal_id = s.signal_id LIMIT 1) as theme,
            r.scope,
            r.relevance_class,
            r.source,
            r.url,
            s.remembered,
            s.forgot as forgotten,
            r.created_at,
            r.lang,
            1 - (s.embedding <=> CAST(:emb AS halfvec(384))) as similarity
        FROM signals s
        JOIN raw_records r ON s.record_id = r.record_id
        WHERE {where_sql}
        ORDER BY s.embedding <=> CAST(:emb AS halfvec(384))
        LIMIT :lim
    """

    rows = await execute_query(query, params)

    # Filter by similarity threshold and deduplicate by summary
    seen_summaries: set[str] = set()
    results = []
    for row in rows:
        sim = float(row.get("similarity", 0))
        if sim < EPISODE_SIMILARITY_THRESHOLD:
            continue
        # Deduplicate by summary
        summary_key = row["summary"][:100].lower().strip()
        if summary_key in seen_summaries:
            continue
        seen_summaries.add(summary_key)
        row["similarity"] = sim
        results.append(row)

    return results


async def retrieve_literature(
    query_embedding: list[float],
    limit: int = 4,
) -> list[dict]:
    """Retrieve top literature chunks by cosine similarity."""
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    query = """
        SELECT
            lc.source_id,
            lc.text,
            ls.title,
            ls.citation,
            ls.link,
            ls.era,
            ls.tags,
            1 - (lc.embedding <=> CAST(:emb AS halfvec(384))) as similarity
        FROM literature_chunks lc
        JOIN literature_sources ls ON lc.source_id = ls.id
        WHERE lc.embedding IS NOT NULL
        ORDER BY lc.embedding <=> CAST(:emb AS halfvec(384))
        LIMIT :lim
    """

    rows = await execute_query(query, {"emb": embedding_str, "lim": limit})

    results = []
    for row in rows:
        sim = float(row.get("similarity", 0))
        if sim < LITERATURE_SIMILARITY_THRESHOLD:
            continue
        row["similarity"] = sim
        results.append(row)

    return results


# ── Step 4: Fetch precomputed stats snapshot ─────────────────────────────────
async def get_stats_snapshot() -> dict:
    """Fetch a compact snapshot of precomputed stats for counting questions (FR-103)."""
    theme_stats, hypothesis_stats = (
        await execute_query("SELECT name, rank_score, signals as signal_count, scope, evidence_strength FROM themes ORDER BY rank_score DESC LIMIT 20"),
        await execute_query("SELECT h.statement, t.scope, h.details->>'stage' as primary_funnel_stage, h.details->>'why' as why_we_believe_it, h.details->>'counter' as counter_evidence FROM hypotheses h JOIN themes t ON h.theme_id = t.id WHERE h.origin = 'data_derived'"),
    )

    # Compute total signals by scope
    total_core = await fetch_one("SELECT count(*) as c FROM signals s JOIN raw_records r ON s.record_id = r.record_id WHERE s.is_signal = true AND r.scope = 'core'")
    total_adjacent = await fetch_one("SELECT count(*) as c FROM signals s JOIN raw_records r ON s.record_id = r.record_id WHERE s.is_signal = true AND r.scope = 'adjacent'")
    dropped = await fetch_one("SELECT count(*) as c FROM signals WHERE is_signal = false")
    
    # Outcome counts from signals
    outcome_counts_rows = await execute_query("SELECT outcome, count(*) as count FROM signals WHERE is_signal = true AND outcome IS NOT NULL GROUP BY outcome")
    outcome_counts = {row["outcome"]: row["count"] for row in outcome_counts_rows}

    return {
        "total_signals": (total_core["c"] if total_core else 0) + (total_adjacent["c"] if total_adjacent else 0),
        "total_core_signals": total_core["c"] if total_core else 0,
        "total_adjacent_signals": total_adjacent["c"] if total_adjacent else 0,
        "dropped_at_signals": dropped["c"] if dropped else 0,
        "outcome_counts": outcome_counts,
        "themes": [
            {
                "name": t["name"],
                "rank_score": float(t["rank_score"]) if t["rank_score"] else 0,
                "signal_count": t["signal_count"],
                "scope": t["scope"],
                "evidence_strength": t["evidence_strength"],
            }
            for t in theme_stats
        ],
        "hypotheses": [
            {
                "statement": h["statement"],
                "scope": h["scope"],
                "primary_funnel_stage": h["primary_funnel_stage"],
                "why_we_believe_it": h["why_we_believe_it"],
                "counter_evidence": h["counter_evidence"],
            }
            for h in hypothesis_stats
        ],
    }


# ── Step 5: Generate answer with Gemini ──────────────────────────────────────
def generate_answer(
    question: str,
    rewritten_query: str,
    episodes: list[dict],
    literature: list[dict],
    stats: dict,
    insufficient_evidence: bool = False,
) -> str:
    """Use Gemini to generate an answer from the retrieved context."""

    # Build episode context
    episode_context_parts = []
    for i, ep in enumerate(episodes, 1):
        date_str = ""
        if ep.get("created_at"):
            try:
                date_str = str(ep["created_at"])[:10]
            except Exception:
                date_str = str(ep.get("created_at", ""))
        parts = [
            f"[E{i}] Signal: {ep.get('summary', 'unknown')}",
            f"  Quote (EN): \"{ep.get('quote', 'unknown')}\"",
        ]
        if ep.get("quote_original") and ep["quote_original"] != ep.get("quote"):
            parts.append(f"  Quote (original): \"{ep['quote_original']}\"")
        parts.extend([
            f"  Theme: {ep.get('theme', 'unknown')}",
            f"  Scope: {ep.get('scope', 'unknown')}",
            f"  Relevance Class: {ep.get('relevance_class', 'unknown')}",
            f"  Source: {ep.get('source', 'unknown')}",
            f"  Date: {date_str}",
        ])
        if ep.get("remembered"):
            parts.append(f"  Remembered Cues: {ep['remembered']}")
        if ep.get("forgotten"):
            parts.append(f"  Forgotten Cues: {ep['forgotten']}")
        episode_context_parts.append("\n".join(parts))

    # Build literature context
    lit_context_parts = []
    for i, lit in enumerate(literature, 1):
        parts = [
            f"[R{i}] Research: {lit['title']}",
            f"  Summary: {lit['text'][:500]}",
            f"  Era: {lit.get('era', 'unknown')}",
        ]
        lit_context_parts.append("\n".join(parts))

    # Build stats context
    stats_text = json.dumps(stats, indent=None, default=str)

    system = f"""You are a research assistant answering questions about user photo retrieval experiences.
You answer ONLY from the provided context (signals and research). Never invent information.

CITATION RULES:
- Cite signals as [E1], [E2], etc. inline in your answer.
- Cite research as [R1], [R2], etc. inline in your answer.
- Every factual claim must have at least one citation.
- Only use citation IDs that exist in the provided context.

STATS RULES:
- For "how many" or counting questions, use the PRECOMPUTED STATS section below.
- When using stats numbers, explicitly state: "According to precomputed stats across all {stats.get('total_signals', 0)} signals, ..."
- Do NOT count from the retrieved signals sample for aggregate numbers.

{"IMPORTANT: There is not enough user evidence (fewer than 3 relevant signals found). State this clearly. If research citations are available, share relevant research findings." if insufficient_evidence else ""}

Answer concisely but thoroughly. Use plain language suitable for a PM audience."""

    prompt_parts = [f"Question: {question}", f"Rewritten search query: {rewritten_query}"]

    if episode_context_parts:
        prompt_parts.append("\n--- USER SIGNALS ---\n" + "\n\n".join(episode_context_parts))

    if lit_context_parts:
        prompt_parts.append("\n--- RESEARCH ---\n" + "\n\n".join(lit_context_parts))

    prompt_parts.append(f"\n--- PRECOMPUTED STATS ---\n{stats_text}")
    prompt_parts.append("\nAnswer:")

    prompt = "\n\n".join(prompt_parts)

    return _call_gemini(prompt, system_instruction=system, temperature=0.3)


# ── Step 6: Validate citations ───────────────────────────────────────────────
def validate_citations(
    answer: str,
    num_episodes: int,
    num_literature: int,
) -> str:
    """Strip invalid citation IDs from the answer (FR-101)."""
    valid_episode_ids = {f"E{i}" for i in range(1, num_episodes + 1)}
    valid_lit_ids = {f"R{i}" for i in range(1, num_literature + 1)}
    valid_ids = valid_episode_ids | valid_lit_ids

    def replace_citation(match: re.Match) -> str:
        # Expand grouped references so every valid ID gets a citation card.
        ids = re.findall(r"[ER]\d+", match.group(1))
        return " ".join(f"[{cid}]" for cid in ids if cid in valid_ids)

    # Match individual references and groups such as [E1, E2, R3].
    cleaned = re.sub(r"\[([ER]\d+(?:\s*,\s*[ER]\d+)*)\]", replace_citation, answer)
    # Clean up any double spaces left by stripping
    cleaned = re.sub(r"  +", " ", cleaned)
    return cleaned.strip()


# ── Cache helpers ────────────────────────────────────────────────────────────
def _question_hash(question: str) -> str:
    """Hash a question for cache lookup."""
    normalized = question.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


async def get_cached_response(question: str) -> dict | None:
    """Check chat_cache for a cached response within TTL (FR-106)."""
    qhash = _question_hash(question)
    row = await fetch_one(
        "SELECT response, created_at FROM chat_cache WHERE question_hash = :qhash",
        {"qhash": qhash},
    )
    if not row:
        return None

    created = row["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) - created > timedelta(days=CACHE_TTL_DAYS):
        return None

    response = row["response"]
    if isinstance(response, str):
        response = json.loads(response)
    return response


async def cache_response(question: str, response: dict) -> None:
    """Store a response in chat_cache."""
    qhash = _question_hash(question)
    response_json = json.dumps(response, default=str)
    await execute_query(
        """
        INSERT INTO chat_cache (question_hash, response, created_at)
        VALUES (:qhash, CAST(:response AS jsonb), NOW())
        ON CONFLICT (question_hash)
        DO UPDATE SET response = CAST(:response AS jsonb), created_at = NOW()
        """,
        {"qhash": qhash, "response": response_json},
    )


# ── Main chat handler ────────────────────────────────────────────────────────
async def handle_chat(
    question: str,
    embedding_model: Any,
    filters: dict | None = None,
) -> dict:
    """
    Full RAG chat pipeline (FR-100).

    Returns a ChatResponse dict with answer, citations, literature_citations,
    rewritten_query, stats_used, and cached status.
    """
    # Check cache first
    cached = await get_cached_response(question)
    # Older cached answers can contain grouped references without citation cards.
    # Regenerate these rather than returning incomplete evidence metadata.
    if cached and not re.search(r"\[[ER]\d+\s*,", cached.get("answer", "")):
        cached["cached"] = True
        return cached

    # Step 1: Rewrite query
    rewritten = await asyncio.to_thread(rewrite_query, question)
    logger.info("Rewritten query: %s", rewritten)

    # Step 2: Embed
    query_embedding = await asyncio.to_thread(embed_query, rewritten, embedding_model)

    # Step 3: Retrieve
    episodes = await retrieve_episodes(query_embedding, limit=12, filters=filters)
    literature = await retrieve_literature(query_embedding, limit=4)

    insufficient = len(episodes) < MIN_EPISODES_FOR_SUFFICIENT

    # Step 4: Stats snapshot
    stats = await get_stats_snapshot()

    # Step 5: Generate answer
    raw_answer = await asyncio.to_thread(
        generate_answer,
        question=question,
        rewritten_query=rewritten,
        episodes=episodes,
        literature=literature,
        stats=stats,
        insufficient_evidence=insufficient,
    )

    # Step 6: Validate citations
    answer = validate_citations(raw_answer, len(episodes), len(literature))

    # Build citations list (FR-104)
    citations = []
    for i, ep in enumerate(episodes, 1):
        citation_id = f"E{i}"
        # Only include if actually cited in the answer
        if f"[{citation_id}]" in answer:
            date_str = ""
            if ep.get("created_at"):
                try:
                    date_str = str(ep["created_at"])[:10]
                except Exception:
                    date_str = ""
            cit: dict[str, Any] = {
                "id": citation_id,
                "signal_id": ep["signal_id"],
                "quote_en": ep.get("quote", ""),
                "source": ep.get("source", ""),
                "url": ep.get("url", ""),
                "date": date_str,
            }
            if ep.get("quote_original") and ep["quote_original"] != ep.get("quote"):
                cit["quote_original"] = ep["quote_original"]
            citations.append(cit)

    # Build literature citations
    literature_citations = []
    for i, lit in enumerate(literature, 1):
        citation_id = f"R{i}"
        if f"[{citation_id}]" in answer:
            literature_citations.append({
                "id": citation_id,
                "title": lit["title"],
                "era": lit.get("era", ""),
                "link": lit.get("link", ""),
            })

    response = {
        "answer": answer,
        "citations": citations,
        "literature_citations": literature_citations,
        "rewritten_query": rewritten,
        "stats_used": True,
        "cached": False,
        "insufficient_evidence": insufficient,
    }

    # Cache the response
    try:
        await cache_response(question, response)
    except Exception as e:
        logger.warning("Failed to cache chat response: %s", e)

    return response
