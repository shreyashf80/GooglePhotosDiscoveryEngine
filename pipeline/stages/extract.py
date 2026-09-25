"""
Stage 2: Episode extraction — Gemini structured extraction with validation and retry.

References:
  FR-40  — Gemini extracts in batches using structured output with Pydantic schema
  FR-41  — English output fields validated
  FR-42  — Schema validation with retry (error appended)
  FR-43  — 0–3 episodes per record; general complaints get general_failure_modes
  FR-44  — Cues, forgotten cues, queries in normalized child tables
  FR-45  — prompt_version and model_id stored per episode
  FR-46  — Emergent label tracking
  FR-20  — Processes status=filtered, advances status
  FR-6   — Writes pipeline_runs row
  FR-54  — Prompts from versioned files
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import ValidationError
from sqlalchemy import text

from pipeline.config import (
    EXTRACT_BATCH_SIZE,
    GEMINI_EXTRACT_MODEL,
    GEMINI_RPM_PER_KEY,
    GEMINI_API_KEYS,
    MAX_EXTRACT_RETRIES,
    PROMPTS_DIR,
    require_model_id,
)
from pipeline.db import engine
from pipeline.llm.client import GeminiClient
from pipeline.llm.key_pool import KeyPool
from shared.models import RecordExtraction

logger = logging.getLogger(__name__)

PROMPT_VERSION = "extract_v1"


# ---------------------------------------------------------------------------
# English detection helper (FR-41, T-2.10)
# ---------------------------------------------------------------------------

def _is_likely_english(text_val: str) -> bool:
    """Check if text is likely English using langdetect + Devanagari check."""
    if not text_val or len(text_val.strip()) < 10:
        return True  # Too short to detect, assume OK
    import re
    # Quick check: if text contains Devanagari characters, it's not English
    if re.search(r'[\u0900-\u097F]', text_val):
        return False
    try:
        from langdetect import detect
        lang = detect(text_val)
        return lang == "en"
    except Exception:
        return True  # Detection failure → don't penalize


def _validate_english_outputs(extraction: RecordExtraction) -> RecordExtraction:
    """
    Validate English output fields (FR-41, T-2.10).
    Downgrade extraction_confidence to 'low' if non-English detected.
    """
    for ep in extraction.episodes:
        needs_downgrade = False

        # Check summary_en
        if ep.summary_en and not _is_likely_english(ep.summary_en):
            logger.warning(
                "Non-English summary_en in record %s episode", extraction.record_id
            )
            needs_downgrade = True

        # Check quote_en
        if ep.quote_en and not _is_likely_english(ep.quote_en):
            logger.warning(
                "Non-English quote_en in record %s episode", extraction.record_id
            )
            needs_downgrade = True

        # Check target_description
        if ep.target_description and not _is_likely_english(ep.target_description):
            needs_downgrade = True

        # Check cue values
        for cue in ep.cues_remembered:
            if cue.value and not _is_likely_english(cue.value):
                needs_downgrade = True
                break

        if needs_downgrade:
            ep.extraction_confidence = "low"

    return extraction


# ---------------------------------------------------------------------------
# Emergent label tracking (T-2.8, FR-46)
# ---------------------------------------------------------------------------

def _track_emergent_labels(episodes_data: list[dict]) -> None:
    """Insert/update emergent_labels table for emergent archetype episodes."""
    emergent_labels: dict[str, int] = {}
    for ep in episodes_data:
        if ep.get("archetype_primary") == "emergent" and ep.get("emergent_label"):
            label = ep["emergent_label"].strip().lower()
            emergent_labels[label] = emergent_labels.get(label, 0) + 1

    if not emergent_labels:
        return

    try:
        with engine.begin() as conn:
            for label, count in emergent_labels.items():
                conn.execute(
                    text("""
                        INSERT INTO emergent_labels (label, episode_count, status)
                        VALUES (:label, :count, 'pending')
                        ON CONFLICT (label) DO UPDATE SET
                            episode_count = emergent_labels.episode_count + :count
                    """),
                    {"label": label, "count": count},
                )
    except Exception as e:
        logger.warning("Failed to track emergent labels: %s", e)


# ---------------------------------------------------------------------------
# Episode persistence (T-2.5c)
# ---------------------------------------------------------------------------

def _persist_extraction(
    record_id: str,
    extraction: RecordExtraction,
    prompt_version: str,
    model_id: str,
    conn,
) -> int:
    """
    Write validated episodes and child tables in a single transaction.
    Returns count of episodes written.
    """
    episodes_written = 0

    # Delete existing episodes and cascading child rows before re-extracting
    conn.execute(
        text("DELETE FROM episodes WHERE record_id = :id"),
        {"id": record_id}
    )

    # Handle general_search_complaint with 0 episodes (T-2.11, FR-43)
    if extraction.general_failure_modes:
        failure_modes_list = [
            fm.value if hasattr(fm, "value") else str(fm)
            for fm in extraction.general_failure_modes
        ]
        conn.execute(
            text("""
                UPDATE raw_records
                SET general_failure_modes = :modes
                WHERE record_id = :id
            """),
            {
                "modes": failure_modes_list,
                "id": record_id,
            },
        )

    # Update record-level fields
    conn.execute(
        text("""
            UPDATE raw_records
            SET platform = :platform,
                mentions_ask_photos = :mentions_ask_photos,
                ask_photos_note = :ask_photos_note
            WHERE record_id = :id
        """),
        {
            "platform": extraction.platform.value if hasattr(extraction.platform, "value") else str(extraction.platform),
            "mentions_ask_photos": extraction.mentions_ask_photos,
            "ask_photos_note": extraction.ask_photos_note,
            "id": record_id,
        },
    )

    # Write episodes
    for ep_no, ep in enumerate(extraction.episodes, start=1):
        episode_id = f"{record_id}_e{ep_no}"

        # Get enum values safely
        def _val(v):
            return v.value if hasattr(v, "value") else str(v)

        failure_modes_list = [_val(fm) for fm in ep.failure_modes]
        workarounds_list = [_val(w) for w in ep.workarounds]
        role_hints_list = [_val(r) for r in ep.role_hints]

        conn.execute(
            text("""
                INSERT INTO episodes (
                    episode_id, record_id, episode_no,
                    target_description, photo_category, photo_origin,
                    photo_age_bucket, photo_age_evidence,
                    failure_modes, workarounds,
                    outcome, stakes, role_hints,
                    archetype_primary, archetype_secondary, emergent_label,
                    summary_en, quote_original, quote_en,
                    extraction_confidence, prompt_version, model_id
                ) VALUES (
                    :episode_id, :record_id, :episode_no,
                    :target_description, :photo_category, :photo_origin,
                    :photo_age_bucket, :photo_age_evidence,
                    :failure_modes, :workarounds,
                    :outcome, :stakes, :role_hints,
                    :archetype_primary, :archetype_secondary, :emergent_label,
                    :summary_en, :quote_original, :quote_en,
                    :extraction_confidence, :prompt_version, :model_id
                )
                ON CONFLICT (episode_id) DO UPDATE SET
                    target_description = EXCLUDED.target_description,
                    photo_category = EXCLUDED.photo_category,
                    summary_en = EXCLUDED.summary_en,
                    extraction_confidence = EXCLUDED.extraction_confidence
            """),
            {
                "episode_id": episode_id,
                "record_id": record_id,
                "episode_no": ep_no,
                "target_description": ep.target_description,
                "photo_category": _val(ep.photo_category),
                "photo_origin": _val(ep.photo_origin),
                "photo_age_bucket": _val(ep.photo_age_bucket) if ep.photo_age_bucket else "unknown",
                "photo_age_evidence": ep.photo_age_evidence,
                "failure_modes": failure_modes_list,
                "workarounds": workarounds_list,
                "outcome": _val(ep.outcome),
                "stakes": _val(ep.stakes),
                "role_hints": role_hints_list,
                "archetype_primary": _val(ep.archetype_primary),
                "archetype_secondary": _val(ep.archetype_secondary) if ep.archetype_secondary else None,
                "emergent_label": ep.emergent_label,
                "summary_en": ep.summary_en,
                "quote_original": ep.quote_original,
                "quote_en": ep.quote_en,
                "extraction_confidence": _val(ep.extraction_confidence),
                "prompt_version": prompt_version,
                "model_id": model_id,
            },
        )

        # Write cues (episode_cues)
        for cue in ep.cues_remembered:
            conn.execute(
                text("""
                    INSERT INTO episode_cues (episode_id, cue_type, value, precision)
                    VALUES (:eid, :cue_type, :value, :precision)
                """),
                {
                    "eid": episode_id,
                    "cue_type": _val(cue.cue_type),
                    "value": cue.value,
                    "precision": _val(cue.precision),
                },
            )

        # Write forgotten cues (episode_forgotten)
        for fc in ep.cues_forgotten:
            conn.execute(
                text("""
                    INSERT INTO episode_forgotten (episode_id, cue_type, evidence)
                    VALUES (:eid, :cue_type, :evidence)
                """),
                {
                    "eid": episode_id,
                    "cue_type": _val(fc.cue_type),
                    "evidence": fc.evidence,
                },
            )

        # Write queries (episode_queries)
        for pos, q in enumerate(ep.queries_tried, start=1):
            conn.execute(
                text("""
                    INSERT INTO episode_queries (episode_id, query_text, query_style, position)
                    VALUES (:eid, :query_text, :query_style, :position)
                """),
                {
                    "eid": episode_id,
                    "query_text": q.query_text,
                    "query_style": _val(q.query_style),
                    "position": pos,
                },
            )

        episodes_written += 1

    return episodes_written


# ---------------------------------------------------------------------------
# Main extract function
# ---------------------------------------------------------------------------

def run_extract(limit: Optional[int] = None) -> dict:
    """
    Run Stage 2 episode extraction on filtered records.

    1. Read status=filtered records.
    2. Send to Gemini in batches of EXTRACT_BATCH_SIZE.
    3. Validate response against Pydantic schema.
    4. On validation failure, retry with error appended (max MAX_EXTRACT_RETRIES).
    5. Write episodes and child tables.
    6. Advance records to status=extracted or status=extract_failed.

    Args:
        limit: If set, process at most this many records.

    Returns:
        Dict with counts.
    """
    model_id = require_model_id("GEMINI_EXTRACT_MODEL")
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    counts = {
        "records_processed": 0,
        "episodes_created": 0,
        "records_extracted": 0,
        "records_failed": 0,
        "validation_retries": 0,
        "general_complaints": 0,
    }
    
    total_tokens = {"input_tokens": 0, "output_tokens": 0}

    # Insert initial pipeline_runs row
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO pipeline_runs (run_id, stage, source, started_at, status)
                VALUES (:run_id, 'extract', 'all', :started_at, 'running')
            """),
            {"run_id": run_id, "started_at": started_at},
        )

    # Load prompt template
    prompt_path = PROMPTS_DIR / "extract_v1.md"
    prompt_template = prompt_path.read_text()

    # Initialize LLM client
    key_pool = KeyPool(keys=GEMINI_API_KEYS, rpm_per_key=GEMINI_RPM_PER_KEY)
    client = GeminiClient(key_pool=key_pool, model_id=model_id)

    try:
        # Load filtered records
        with engine.begin() as conn:
            query = """
                SELECT record_id, source, created_at, lang, relevance_class, text, retry_count
                FROM raw_records
                WHERE status = 'filtered'
                ORDER BY created_at DESC NULLS LAST
            """
            if limit:
                query += f" LIMIT {int(limit)}"
            result = conn.execute(text(query))
            all_records = result.fetchall()

        logger.info("Extract: loaded %d filtered records", len(all_records))

        if not all_records:
            logger.info("Extract: no records to process")
            return counts

        # Process in batches
        batch_size = EXTRACT_BATCH_SIZE
        for i in range(0, len(all_records), batch_size):
            batch = all_records[i : i + batch_size]
            counts["records_processed"] += len(batch)

            # Build the prompt input — fields per user spec for extract
            records_for_prompt = []
            for row in batch:
                created_at_str = ""
                if row.created_at:
                    if isinstance(row.created_at, datetime):
                        created_at_str = row.created_at.strftime("%Y-%m-%d")
                    else:
                        created_at_str = str(row.created_at)[:10]

                records_for_prompt.append({
                    "record_id": row.record_id,
                    "source": row.source or "",
                    "created_at": created_at_str,
                    "lang": row.lang or "en",
                    "relevance_class": row.relevance_class or "specific_episode",
                    "text": row.text or "",
                })

            records_json = json.dumps(records_for_prompt, ensure_ascii=False, indent=2)
            prompt = prompt_template.replace("{{RECORDS_JSON}}", records_json)

            # Attempt extraction with retries
            response = None
            last_error = None
            
            for attempt in range(MAX_EXTRACT_RETRIES):
                try:
                    if attempt > 0:
                        # Append error to prompt on retry (FR-42)
                        retry_prompt = (
                            prompt
                            + f"\n\n[VALIDATION ERROR from previous attempt: {last_error}]\n"
                            + "Please fix the error and return valid JSON.\n"
                        )
                        response = client.generate(
                            prompt=retry_prompt,
                            response_schema=list[RecordExtraction],
                            temperature=0.1,
                        )
                        counts["validation_retries"] += 1
                    else:
                        response = client.generate(
                            prompt=prompt,
                            response_schema=list[RecordExtraction],
                            temperature=0.1,
                        )
                        
                    total_tokens["input_tokens"] += client.last_tokens.get("input_tokens", 0)
                    total_tokens["output_tokens"] += client.last_tokens.get("output_tokens", 0)
                    
                    # Validate immediately so errors trigger a retry
                    results_list = response if isinstance(response, list) else [response]
                    for item in results_list:
                        if isinstance(item, dict):
                            RecordExtraction.model_validate(item)
                            
                    break  # Success
                except Exception as e:
                    last_error = str(e)[:500]
                    logger.warning(
                        "Extract batch %d-%d attempt %d failed: %s",
                        i, i + len(batch), attempt + 1, last_error,
                    )
                    if attempt == MAX_EXTRACT_RETRIES - 1:
                        response = None

            if response is None:
                # All retries failed — mark all records in batch as extract_failed
                logger.error("Extract batch %d-%d: all retries exhausted", i, i + len(batch))
                with engine.begin() as conn:
                    for row in batch:
                        conn.execute(
                            text("""
                                UPDATE raw_records
                                SET status = CASE WHEN COALESCE(retry_count, 0) >= 2 THEN 'extract_failed' ELSE 'filtered' END,
                                    retry_count = COALESCE(retry_count, 0) + 1,
                                    last_error = :error,
                                    run_id = :run_id
                                WHERE record_id = :id
                            """),
                            {
                                "id": row.record_id,
                                "error": last_error or "All extraction attempts failed",
                                "run_id": run_id,
                            },
                        )
                        counts["records_failed"] += 1
                continue

            # Parse and validate each extraction result
            results_list = response if isinstance(response, list) else [response]

            # Map results by record_id
            results_by_id: dict[str, dict] = {}
            for item in results_list:
                if isinstance(item, dict):
                    rid = item.get("record_id", "")
                    results_by_id[rid] = item
                elif isinstance(item, RecordExtraction):
                    results_by_id[item.record_id] = item.model_dump()

            # Process each record in the batch
            with engine.begin() as conn:
                all_episodes_data = []
                for row in batch:
                    rid = row.record_id
                    if rid not in results_by_id:
                        logger.warning("Extract: record %s missing from LLM response", rid)
                        conn.execute(
                            text("""
                                UPDATE raw_records
                                SET status = CASE WHEN COALESCE(retry_count, 0) >= 2 THEN 'extract_failed' ELSE 'filtered' END,
                                    retry_count = COALESCE(retry_count, 0) + 1,
                                    last_error = 'Missing from LLM response',
                                    run_id = :run_id
                                WHERE record_id = :id
                            """),
                            {"id": rid, "run_id": run_id},
                        )
                        counts["records_failed"] += 1
                        continue

                    raw_result = results_by_id[rid]

                    # Validate via Pydantic
                    try:
                        if isinstance(raw_result, dict):
                            extraction = RecordExtraction.model_validate(raw_result)
                        else:
                            extraction = raw_result
                    except (ValidationError, Exception) as e:
                        logger.warning(
                            "Extract: validation failed for record %s: %s",
                            rid, str(e)[:200],
                        )
                        conn.execute(
                            text("""
                                UPDATE raw_records
                                SET status = CASE WHEN COALESCE(retry_count, 0) >= 2 THEN 'extract_failed' ELSE 'filtered' END,
                                    retry_count = COALESCE(retry_count, 0) + 1,
                                    last_error = :error,
                                    run_id = :run_id
                                WHERE record_id = :id
                            """),
                            {"id": rid, "error": str(e)[:500], "run_id": run_id},
                        )
                        counts["records_failed"] += 1
                        continue

                    # English output validation (T-2.10, FR-41)
                    extraction = _validate_english_outputs(extraction)

                    # Persist episodes and child tables
                    try:
                        ep_count = _persist_extraction(
                            record_id=rid,
                            extraction=extraction,
                            prompt_version=PROMPT_VERSION,
                            model_id=model_id,
                            conn=conn,
                        )

                        # Advance status
                        conn.execute(
                            text("""
                                UPDATE raw_records
                                SET status = 'extracted',
                                    run_id = :run_id
                                WHERE record_id = :id
                            """),
                            {"id": rid, "run_id": run_id},
                        )

                        counts["episodes_created"] += ep_count
                        counts["records_extracted"] += 1

                        if ep_count == 0 and extraction.general_failure_modes:
                            counts["general_complaints"] += 1

                        # Collect episodes for emergent tracking
                        for ep in extraction.episodes:
                            ep_data = ep.model_dump() if hasattr(ep, "model_dump") else ep
                            all_episodes_data.append(ep_data)

                    except Exception as e:
                        logger.error(
                            "Extract: persistence failed for record %s: %s",
                            rid, str(e)[:200],
                        )
                        conn.execute(
                            text("""
                                UPDATE raw_records
                                SET status = CASE WHEN COALESCE(retry_count, 0) >= 2 THEN 'extract_failed' ELSE 'filtered' END,
                                    retry_count = COALESCE(retry_count, 0) + 1,
                                    last_error = :error,
                                    run_id = :run_id
                                WHERE record_id = :id
                            """),
                            {"id": rid, "error": str(e)[:500], "run_id": run_id},
                        )
                        counts["records_failed"] += 1

                # Track emergent labels (T-2.8)
                _track_emergent_labels(all_episodes_data)

            logger.info(
                "Extract batch %d-%d: %d records extracted, %d episodes",
                i, i + len(batch),
                sum(1 for row in batch if row.record_id in results_by_id),
                counts["episodes_created"],
            )

    finally:
        # Write pipeline_runs row (T-2.5d, FR-6)
        ended_at = datetime.now(timezone.utc)
        run_status = "completed" if counts["records_failed"] == 0 else "completed_with_errors"
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

    logger.info("Extract stage complete: %s", counts)
    return counts
