"""
Pipeline configuration — loads all env vars, validates at import time.

References:
  FR-2   — 24-month cutoff
  FR-7   — per-source caps
  FR-52  — per-key RPM ceiling
  FR-53  — model IDs from env vars
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Required environment variable {key} is not set")
    return val


def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


# --- Database ---
DATABASE_URL: str = _require_env("DATABASE_URL")
DATABASE_URL_DIRECT: str = os.getenv("DATABASE_URL_DIRECT", DATABASE_URL)

# --- Gemini LLM ---
GEMINI_API_KEYS: list[str] = [
    k.strip() for k in _require_env("GEMINI_API_KEYS").split(",") if k.strip()
]
GEMINI_FILTER_MODEL: str = os.getenv("GEMINI_FILTER_MODEL", "")
GEMINI_EXTRACT_MODEL: str = os.getenv("GEMINI_EXTRACT_MODEL", "")
GEMINI_CHAT_MODEL: str = os.getenv("GEMINI_CHAT_MODEL", "")
GEMINI_RPM_PER_KEY: int = _env_int("GEMINI_RPM_PER_KEY", 15)


def require_model_id(model_var: str) -> str:
    """Validate that a model ID is set. Call this at LLM stage entry, not import."""
    val = globals().get(model_var, "") or os.getenv(model_var, "")
    if not val:
        raise RuntimeError(
            f"{model_var} is not set. Add it to .env or set the environment variable."
        )
    return val

# --- Source API keys ---
APIFY_TOKEN: str = os.getenv("APIFY_TOKEN", "")
SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")

APPSTORE_PRODUCT_ID: str = os.getenv("APPSTORE_PRODUCT_ID", "962194608")

# --- Time cutoff (FR-2): only records from the last 24 months ---
def get_time_cutoff() -> datetime:
    """Compute 24-month cutoff at run time (FR-2)."""
    return datetime.now(timezone.utc) - timedelta(days=730)


TIME_CUTOFF: datetime = get_time_cutoff()

# --- Source caps (FR-7) ---
SOURCE_CAPS: dict[str, int] = {
    "reddit": _env_int("CAP_REDDIT", 20),
    "playstore": _env_int("CAP_PLAYSTORE", 50),
    "appstore": _env_int("CAP_APPSTORE", 2),
    "youtube": _env_int("CAP_YOUTUBE", 2),
    "community": _env_int("CAP_COMMUNITY", 500),
    "hn": _env_int("CAP_HN", 500),
}

# --- Batch sizes ---
FILTER_BATCH_SIZE: int = _env_int("FILTER_BATCH_SIZE", 25)
EXTRACT_BATCH_SIZE: int = _env_int("EXTRACT_BATCH_SIZE", 10)
EMBED_BATCH_SIZE: int = _env_int("EMBED_BATCH_SIZE", 100)

# --- Retry limits ---
MAX_EXTRACT_RETRIES: int = _env_int("MAX_EXTRACT_RETRIES", 3)

# --- Paths ---
PROJECT_ROOT: Path = _project_root
MIGRATIONS_DIR: Path = _project_root / "db" / "migrations"
SEEDS_DIR: Path = _project_root / "db" / "seeds"
PROMPTS_DIR: Path = _project_root / "pipeline" / "prompts"

# --- FR-30: Keyword prefilter lists ---
# Broad lists for English, Hindi (Devanagari), and Hinglish (Latin).
# When in doubt, include the word — Stage 1 LLM will do precise classification.

KEYWORD_PREFILTER_EN: list[str] = [
    # Core retrieval terms
    "find", "search", "locate", "looking for", "can't see", "where is",
    "scroll", "lost track", "remember", "old photo", "old pic",
    "ask photos",
    # Expanded retrieval and discovery terms
    "can't find", "cannot find", "couldn't find", "unable to find",
    "not finding", "not showing", "won't show", "doesn't show",
    "missing photo", "missing picture", "missing image",
    "photo search", "image search", "picture search",
    "search bar", "search feature", "search function", "search result",
    "no results", "zero results", "wrong results", "irrelevant results",
    "too many results", "too many photos",
    "how do i find", "how to find", "how to search", "how do i search",
    "hard to find", "difficult to find", "impossible to find",
    "found it", "found the photo", "finally found",
    "tried searching", "searched for", "when i search",
    "face recognition", "face search", "face grouping",
    "text search", "ocr", "text in photo",
    "ask photo", "gemini photo", "ai search",
    "specific photo", "particular photo", "certain photo",
    "years ago", "months ago", "long time ago",
    "scrolling", "scroll through", "scrolled",
    "timeline", "date filter", "date search",
    "gave up", "give up", "stopped trying",
    "workaround", "work around",
    "tip", "trick", "pro tip",
    "receipt", "document", "medicine", "prescription",
    "screenshot", "whatsapp photo", "received photo",
    "sent me", "shared with me",
]

KEYWORD_PREFILTER_HI: list[str] = [
    # Hindi (Devanagari)
    "फोटो", "ढूंढ", "खोज", "नहीं मिल", "तस्वीर",
    "तलाश", "ढूंढना", "खोजना", "मिल नहीं",
    "पुरानी फोटो", "पुरानी तस्वीर",
    "सर्च", "रिजल्ट",
    "याद", "कहाँ", "कहां",
    "स्क्रॉल", "स्क्रीनशॉट",
    "दवाई", "रसीद", "डॉक्यूमेंट",
]

KEYWORD_PREFILTER_HINGLISH: list[str] = [
    # Hinglish (Hindi in Latin script)
    "dhoond", "dhund", "dhundh", "dhoondh",
    "nahi mil", "nhi mil", "nahin mil",
    "khoj", "khoji",
    "photo nahi", "pic nahi", "photo nhi",
    "purani photo", "purani pic",
    "kaha hai", "kahan hai", "kidhar",
    "mil nahi raha", "mil nahi rahi", "milta nahi", "milti nahi",
    "search kar", "search kiya", "search karo",
    "scroll kar", "scroll kiya",
    "yaad", "yaad hai",
    "woh photo", "wo photo", "woh pic",
    "screenshot", "whatsapp",
    "dawai", "dawa", "receipt",
]

# Combined keyword set (lowercased for matching)
KEYWORD_PREFILTER_ALL: set[str] = {
    kw.lower() for kw in
    KEYWORD_PREFILTER_EN + KEYWORD_PREFILTER_HI + KEYWORD_PREFILTER_HINGLISH
}
