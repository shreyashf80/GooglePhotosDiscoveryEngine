import os
import pytest
from dotenv import load_dotenv
from pathlib import Path

from urllib.parse import urlparse

# Load .env to get the database URLs
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

test_url = os.environ.get("TEST_DATABASE_URL")
prod_url = os.environ.get("DATABASE_URL")
prod_url_direct = os.environ.get("DATABASE_URL_DIRECT")

# Guard: Abort if TEST_DATABASE_URL is missing
if not test_url:
    pytest.exit("TEST_DATABASE_URL is missing from environment. Aborting tests to protect production database.")

try:
    test_host = urlparse(test_url).hostname
    prod_host = urlparse(prod_url).hostname if prod_url else None
    prod_direct_host = urlparse(prod_url_direct).hostname if prod_url_direct else None
except Exception as e:
    pytest.exit(f"Failed to parse database URLs: {e}")

# Guard: Abort if the test host equals the production DB host
if prod_host and test_host == prod_host:
    pytest.exit("TEST_DATABASE_URL host cannot be the same as DATABASE_URL host. Aborting tests.")
if prod_direct_host and test_host == prod_direct_host:
    pytest.exit("TEST_DATABASE_URL host cannot be the same as DATABASE_URL_DIRECT host. Aborting tests.")

# Override before any app imports so that pipeline.config loads the test DB
os.environ["DATABASE_URL"] = test_url
os.environ["DATABASE_URL_DIRECT"] = test_url

from sqlalchemy import text
from pipeline.db import engine

@pytest.fixture(autouse=True)
def guard_db():
    """Double check that the engine URL is not the prod URL before every test."""
    active_host = engine.url.host
    if prod_host and active_host == prod_host:
        pytest.exit("CRITICAL: pipeline.db.engine is connected to production DATABASE_URL host! Aborting.")
    if prod_direct_host and active_host == prod_direct_host:
        pytest.exit("CRITICAL: pipeline.db.engine is connected to production DATABASE_URL_DIRECT host! Aborting.")

@pytest.fixture
def clean_db():
    """Wipe all tables before and after a test in the test DB."""
    def wipe():
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM episode_queries"))
            conn.execute(text("DELETE FROM episode_forgotten"))
            conn.execute(text("DELETE FROM episode_cues"))
            conn.execute(text("DELETE FROM hypothesis_evidence"))
            conn.execute(text("DELETE FROM episodes"))
            conn.execute(text("DELETE FROM raw_records"))
            conn.execute(text("DELETE FROM pipeline_runs"))
    wipe()
    yield
    wipe()
