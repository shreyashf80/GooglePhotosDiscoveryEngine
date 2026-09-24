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
EXTRACT_BATCH_SIZE: int = _env_int("EXTRACT_BATCH_SIZE", 15)
EMBED_BATCH_SIZE: int = _env_int("EMBED_BATCH_SIZE", 100)

# --- Retry limits ---
MAX_EXTRACT_RETRIES: int = _env_int("MAX_EXTRACT_RETRIES", 3)

# --- Paths ---
PROJECT_ROOT: Path = _project_root
MIGRATIONS_DIR: Path = _project_root / "db" / "migrations"
SEEDS_DIR: Path = _project_root / "db" / "seeds"
PROMPTS_DIR: Path = _project_root / "pipeline" / "prompts"
