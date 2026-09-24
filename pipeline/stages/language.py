import logging
import re
from typing import Optional

from langdetect import detect, LangDetectException
from pipeline.db import engine
from sqlalchemy import text

logger = logging.getLogger(__name__)

DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')

HINGLISH_MARKERS = [
    "kaise", "kare", "kya", "hai", "nahi", "raha", "meri", "mera", "bhai",
    "photo", "dhunde", "mil", "karna", "yeh", "woh", "sirf", "mujhe",
    "kese", "purani", "wali"
]

def detect_language(text_val: str) -> str:
    """
    Detect language (FR-26).
    Returns 'en', 'hi', 'hi-Latn' (Hinglish), or 'other'.
    """
    if not text_val:
        return 'other'
        
    # Check Devanagari first
    if DEVANAGARI_RE.search(text_val):
        return 'hi'
        
    # Simple heuristic for Hinglish
    lower_text = text_val.lower()
    words = set(re.findall(r'\b\w+\b', lower_text))
    hinglish_count = sum(1 for w in words if w in HINGLISH_MARKERS)
    
    if hinglish_count >= 2:
        return 'hi-Latn'
        
    try:
        lang = detect(text_val)
        if lang == 'en':
            return 'en'
        elif lang == 'hi':
            # langdetect might return 'hi' for Romanized Hindi occasionally, but usually it detects Devanagari.
            return 'hi-Latn'
        else:
            return 'other'
    except LangDetectException:
        return 'other'

def run_language_detection() -> dict:
    """
    Language detection stage.
    Runs on status=deduped where lang IS NULL.
    """
    logger.info("Starting Language Detection stage")
    counts = {"processed": 0, "en": 0, "hi": 0, "hi-Latn": 0, "other": 0}
    
    try:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT record_id, text FROM raw_records WHERE status = 'deduped' AND lang IS NULL"))
            records = result.fetchall()
            
            for row in records:
                lang = detect_language(row.text or "")
                conn.execute(
                    text("UPDATE raw_records SET lang = :lang WHERE record_id = :id"),
                    {"lang": lang, "id": row.record_id}
                )
                counts["processed"] += 1
                counts[lang] = counts.get(lang, 0) + 1
                
        logger.info(f"Language detection complete: {counts}")
        return counts
    except Exception as e:
        logger.error(f"Error in language detection stage: {e}")
        return counts
