import os
from pathlib import Path

def test_guard_active():
    from pipeline.db import engine
    from pipeline.config import DATABASE_URL
    
    # Ensure the engine and config use the test URL
    test_url = os.environ.get("TEST_DATABASE_URL")
    assert DATABASE_URL == test_url
    
    # Ensure this is NOT the real production URL from .env
    env_path = Path(__file__).resolve().parent.parent / ".env"
    prod_url = None
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    prod_url = line.strip().split("=", 1)[1]
                    break
    
    from urllib.parse import urlparse
    
    if prod_url:
        prod_host = urlparse(prod_url).hostname
        engine_host = engine.url.host
        assert engine_host != prod_host, "Engine is pointing to the production database host!"
