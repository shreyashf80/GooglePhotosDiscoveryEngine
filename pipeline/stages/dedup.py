import logging
import re
import hashlib
from typing import List

from pipeline.db import engine
from sqlalchemy import text
from shared.enums import Source

logger = logging.getLogger(__name__)

def normalize_text(text_val: str) -> str:
    """Normalize text by lowercasing and stripping whitespace/punctuation."""
    if not text_val:
        return ""
    # Lowercase
    t = text_val.lower()
    # Remove punctuation
    t = re.sub(r'[^\w\s]', '', t)
    # Strip whitespace
    t = re.sub(r'\s+', '', t)
    return t

def truncate_text(text_val: str) -> tuple[str, bool]:
    """Truncate text to 1,500 words."""
    if not text_val:
        return "", False
    words = text_val.split()
    if len(words) > 1500:
        return " ".join(words[:1500]), True
    return text_val, False

def run_dedup() -> dict:
    """
    Dedup stage (FR-24, FR-20) + length filter (FR-27).
    Reads status=raw records, computes normalized hash, removes exact duplicates,
    truncates >1500 words, excludes <20 chars, advances to status=deduped or excluded.
    """
    logger.info("Starting Dedup stage")
    counts = {"processed": 0, "deduped_survivors": 0, "excluded_too_short": 0, "duplicates_dropped": 0, "truncated": 0}
    
    try:
        with engine.begin() as conn:
            # Populate seen hashes from existing records
            seen_hashes = set()
            existing = conn.execute(text("SELECT text FROM raw_records WHERE status != 'raw' AND text IS NOT NULL"))
            for (t,) in existing:
                if t:
                    norm = normalize_text(t)
                    text_hash = hashlib.sha256(norm.encode('utf-8')).hexdigest()
                    seen_hashes.add(text_hash)
                    
            # Get all raw records
            result = conn.execute(text("SELECT record_id, text, source FROM raw_records WHERE status = 'raw'"))
            records = result.fetchall()
            
            for row in records:
                counts["processed"] += 1
                record_id = row.record_id
                original_text = row.text or ""
                
                # Check length (exclude < 20 chars)
                if len(original_text.strip()) < 20:
                    conn.execute(
                        text("UPDATE raw_records SET status = 'excluded', relevance_reason = 'too_short' WHERE record_id = :id"),
                        {"id": record_id}
                    )
                    counts["excluded_too_short"] += 1
                    continue
                
                # Truncate
                processed_text, truncated = truncate_text(original_text)
                if truncated:
                    counts["truncated"] += 1
                
                # Normalize and hash
                norm = normalize_text(processed_text)
                text_hash = hashlib.sha256(norm.encode('utf-8')).hexdigest()
                
                if text_hash in seen_hashes:
                    # Duplicate
                    conn.execute(
                        text("UPDATE raw_records SET status = 'excluded', relevance_reason = 'duplicate' WHERE record_id = :id"),
                        {"id": record_id}
                    )
                    counts["duplicates_dropped"] += 1
                else:
                    # Survivor
                    seen_hashes.add(text_hash)
                    
                    conn.execute(
                        text("UPDATE raw_records SET status = 'deduped', text = :text, text_len = :len, truncated = :trunc WHERE record_id = :id"),
                        {"text": processed_text, "len": len(processed_text), "trunc": truncated, "id": record_id}
                    )
                    counts["deduped_survivors"] += 1
                    
        logger.info(f"Dedup complete: {counts}")
        return counts
    except Exception as e:
        logger.error(f"Error in dedup stage: {e}")
        return counts
