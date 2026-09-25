"""
Stage 1: Relevance filter — keyword prefilter + Gemini batch classification.

References:
  FR-30  — keyword prefilter (English, Hindi, Hinglish)
  FR-31  — Gemini classifies records in batches of ~25
  FR-32  — irrelevant / lost_not_hidden → status=excluded
  FR-20  — processes only status=deduped, advances status
  FR-6   — writes pipeline_runs row
  FR-54  — prompts from versioned files
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import text

from pipeline.config import (
    FILTER_BATCH_SIZE,
    GEMINI_FILTER_MODEL,
    GEMINI_RPM_PER_KEY,
    GEMINI_API_KEYS,
    KEYWORD_PREFILTER_ALL,
    PROMPTS_DIR,
    require_model_id,
)
from pipeline.db import engine
from pipeline.llm.client import GeminiClient
from pipeline.llm.key_pool import KeyPool
from shared.enums import RelevanceClass
from shared.models import FilterResult

logger = logging.getLogger(__name__)

# Prompt version identifier
PROMPT_VERSION = "filter_v1"

# Classes that advance to extraction
RELEVANT_CLASSES = frozenset({
    RelevanceClass.SPECIFIC_EPISODE,
    RelevanceClass.GENERAL_SEARCH_COMPLAINT,
    RelevanceClass.SUCCESS_OR_TIP,
})


# ---------------------------------------------------------------------------
# Pydantic model for Gemini structured output (response schema)
# ---------------------------------------------------------------------------

class FilterResultItem(BaseModel):
    """Single filter result for Gemini structured output."""
    record_id: str
    relevance_class: RelevanceClass
    lang: str
    reason: str


class FilterBatchResponse(BaseModel):
    """Batch of filter results — this is the response schema for Gemini."""
    results: list[FilterResultItem]


# ---------------------------------------------------------------------------
# Keyword prefilter
# ---------------------------------------------------------------------------

def check_keyword_hit(text_val: str) -> bool:
    """Check if text contains any keyword from the prefilter lists (FR-30)."""
    if not text_val:
        return False
    lower = text_val.lower()
    for kw in KEYWORD_PREFILTER_ALL:
        if kw in lower:
            return True
    return False


# ---------------------------------------------------------------------------
# Main filter function
# ---------------------------------------------------------------------------

def run_filter(limit: Optional[int] = None) -> dict:
    """
    Run Stage 1 relevance filter on deduped records.

    1. Set keyword_hit flag on all deduped records.
    2. Exclude English records without keyword hit (skip LLM).
    3. Send remaining records to Gemini in batches of FILTER_BATCH_SIZE.
    4. Set relevance_class, advance status.

    Args:
        limit: If set, process at most this many records.

    Returns:
        Dict with counts of records processed, classified, excluded, etc.
    """
    model_id = require_model_id("GEMINI_FILTER_MODEL")
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    counts = {
        "processed": 0,
        "keyword_hit": 0,
        "keyword_miss_en_excluded": 0,
        "sent_to_llm": 0,
        "classified_relevant": 0,
        "classified_excluded": 0,
        "llm_errors": 0,
    }
    
    total_tokens = {"input_tokens": 0, "output_tokens": 0}

    # Insert initial pipeline_runs row
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO pipeline_runs (run_id, stage, source, started_at, status)
                VALUES (:run_id, 'filter', 'all', :started_at, 'running')
            """),
            {"run_id": run_id, "started_at": started_at},
        )

    # Load prompt template
    prompt_path = PROMPTS_DIR / "filter_v1.md"
    prompt_template = prompt_path.read_text()

    # Initialize LLM client
    key_pool = KeyPool(keys=GEMINI_API_KEYS, rpm_per_key=GEMINI_RPM_PER_KEY)
    client = GeminiClient(key_pool=key_pool, model_id=model_id)

    try:
        # Phase 1: Load deduped records and apply keyword prefilter
        with engine.begin() as conn:
            query = "SELECT record_id, source, lang, text FROM raw_records WHERE status = 'deduped'"
            if limit:
                query += f" LIMIT {int(limit)}"
            result = conn.execute(text(query))
            all_records = result.fetchall()

        logger.info("Filter: loaded %d deduped records", len(all_records))

        # Phase 2: Keyword prefilter — set keyword_hit, exclude EN misses
        to_llm = []
        with engine.begin() as conn:
            for row in all_records:
                counts["processed"] += 1
                record_id = row.record_id
                record_text = row.text or ""
                record_lang = row.lang or "en"
                record_source = row.source or ""

                hit = check_keyword_hit(record_text)

                # Update keyword_hit flag
                conn.execute(
                    text("UPDATE raw_records SET keyword_hit = :hit WHERE record_id = :id"),
                    {"hit": hit, "id": record_id},
                )

                if hit:
                    counts["keyword_hit"] += 1
                    to_llm.append({
                        "record_id": record_id,
                        "source": record_source,
                        "lang": record_lang,
                        "text": record_text,
                    })
                elif record_lang and record_lang != "en":
                    # Non-English without keyword hit still go to LLM (FR-30)
                    to_llm.append({
                        "record_id": record_id,
                        "source": record_source,
                        "lang": record_lang,
                        "text": record_text,
                    })
                else:
                    # English without keyword hit → exclude without LLM
                    conn.execute(
                        text("""
                            UPDATE raw_records
                            SET status = 'excluded',
                                relevance_class = 'irrelevant',
                                relevance_reason = 'keyword_prefilter_miss',
                                run_id = :run_id
                            WHERE record_id = :id
                        """),
                        {"id": record_id, "run_id": run_id},
                    )
                    counts["keyword_miss_en_excluded"] += 1

        logger.info(
            "Filter: %d keyword hits, %d EN excluded, %d to LLM",
            counts["keyword_hit"],
            counts["keyword_miss_en_excluded"],
            len(to_llm),
        )

        # Phase 3: Send to Gemini in batches
        batch_size = FILTER_BATCH_SIZE
        for i in range(0, len(to_llm), batch_size):
            batch = to_llm[i : i + batch_size]
            counts["sent_to_llm"] += len(batch)

            # Build the prompt input — only the fields needed by filter_v1.md
            records_json = json.dumps(
                [
                    {
                        "record_id": r["record_id"],
                        "source": r["source"],
                        "lang": r["lang"],
                        "text": r["text"],
                    }
                    for r in batch
                ],
                ensure_ascii=False,
                indent=2,
            )

            prompt = prompt_template.replace("{{RECORDS_JSON}}", records_json)

            try:
                response = None
                last_err = None
                for attempt in range(3):
                    try:
                        response = client.generate(
                            prompt=prompt,
                            response_schema=list[FilterResultItem],
                            temperature=0.1,
                        )
                        break
                    except Exception as err:
                        print("FILTER ERROR:", err)
                        last_err = err
                        logger.warning("Filter batch %d-%d attempt %d failed: %s", i, i + len(batch), attempt + 1, err)
                        import time
                        time.sleep(2)
                
                if response is None:
                    raise last_err or Exception("All filter batch attempts failed")
                    
                total_tokens["input_tokens"] += client.last_tokens.get("input_tokens", 0)
                total_tokens["output_tokens"] += client.last_tokens.get("output_tokens", 0)

                # Parse results — response is a list of dicts
                results_list = response if isinstance(response, list) else response.get("results", response)

                # Map results by record_id
                results_by_id = {}
                for item in results_list:
                    if isinstance(item, dict):
                        results_by_id[item["record_id"]] = item
                    else:
                        results_by_id[item.record_id] = item

                # Apply results to DB
                with engine.begin() as conn:
                    for r in batch:
                        rid = r["record_id"]
                        if rid in results_by_id:
                            item = results_by_id[rid]
                            if isinstance(item, dict):
                                rel_class = item.get("relevance_class", "irrelevant")
                                reason = item.get("reason", "")
                                lang = item.get("lang", r["lang"])
                            else:
                                rel_class = item.relevance_class
                                reason = item.reason
                                lang = item.lang

                            # Determine new status
                            if rel_class in (
                                "specific_episode",
                                "general_search_complaint",
                                "success_or_tip",
                            ):
                                new_status = "filtered"
                                counts["classified_relevant"] += 1
                            else:
                                new_status = "excluded"
                                counts["classified_excluded"] += 1

                            conn.execute(
                                text("""
                                    UPDATE raw_records
                                    SET status = :status,
                                        relevance_class = :rel_class,
                                        relevance_reason = :reason,
                                        lang = :lang,
                                        run_id = :run_id
                                    WHERE record_id = :id
                                """),
                                {
                                    "status": new_status,
                                    "rel_class": rel_class,
                                    "reason": reason,
                                    "lang": lang,
                                    "id": rid,
                                    "run_id": run_id,
                                },
                            )
                        else:
                            # Record not in response — mark as error
                            logger.warning("Filter: record %s missing from LLM response", rid)
                            conn.execute(
                                text("""
                                    UPDATE raw_records
                                    SET retry_count = COALESCE(retry_count, 0) + 1,
                                        last_error = 'missing_from_llm_response',
                                        run_id = :run_id
                                    WHERE record_id = :id
                                """),
                                {"id": rid, "run_id": run_id},
                            )
                            counts["llm_errors"] += 1

                logger.info(
                    "Filter batch %d-%d: %d results processed",
                    i, i + len(batch), len(results_list),
                )

            except Exception as e:
                logger.error("Filter batch %d-%d failed: %s", i, i + len(batch), e)
                counts["llm_errors"] += len(batch)
                # Mark batch as failed but leave status as is (deduped)
                with engine.begin() as conn:
                    for r in batch:
                        conn.execute(
                            text("""
                                UPDATE raw_records
                                SET retry_count = COALESCE(retry_count, 0) + 1,
                                    last_error = :reason,
                                    run_id = :run_id
                                WHERE record_id = :id
                            """),
                            {"id": r["record_id"], "reason": f"llm_error: {str(e)[:200]}", "run_id": run_id},
                        )

    finally:
        # Write pipeline_runs row (FR-6)
        ended_at = datetime.now(timezone.utc)
        run_status = "completed" if counts["llm_errors"] == 0 else "completed_with_errors"
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE pipeline_runs
                        SET ended_at = :ended_at,
                            counts = :counts,
                            errors = :errors,
                            tokens = :tokens,
                            status = :status
                        WHERE run_id = :run_id
                    """),
                    {
                        "run_id": run_id,
                        "ended_at": ended_at,
                        "counts": json.dumps(counts),
                        "errors": json.dumps([]),
                        "tokens": json.dumps(total_tokens),
                        "status": run_status,
                    },
                )
        except Exception as e:
            logger.error("Failed to write pipeline_runs row: %s", e)

    logger.info("Filter stage complete: %s", counts)
    return counts
