import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import uuid
import json
from sqlalchemy import create_engine, text
from typer.testing import CliRunner

from pipeline.cli import app, redact_secrets

from pipeline.db import engine

def test_redact_secrets(monkeypatch):
    import pipeline.cli
    monkeypatch.setattr(pipeline.cli, "APIFY_TOKEN", "supersecret1")
    monkeypatch.setattr(pipeline.cli, "SERPAPI_KEY", "supersecret2")
    monkeypatch.setattr(pipeline.cli, "YOUTUBE_API_KEY", "supersecret3")
    
    msg = "Error connecting with APIFY_TOKEN supersecret1 and SERPAPI_KEY supersecret2"
    redacted = redact_secrets(msg)
    
    assert "supersecret1" not in redacted
    assert "supersecret2" not in redacted
    assert "***REDACTED***" in redacted

def test_ingest_source_failure_logs_run(clean_db):
    import pipeline.cli
    
    mock_src = MagicMock()
    # Ensure it fails
    mock_src.fetch.side_effect = Exception("Custom source exception")
    
    # We will override the sources_to_run logic in cli by monkeypatching the sources list
    def mock_sources_to_run():
        return [("test_source", mock_src)]
        
    with patch("pipeline.cli.RedditSource", return_value=mock_src):
        runner = CliRunner()
        result = runner.invoke(app, ["ingest", "--source", "reddit"])
        
    assert result.exit_code == 0
    assert "Error ingesting reddit: Custom source exception" in result.output
    
    with engine.begin() as conn:
        run = conn.execute(text("SELECT status, errors FROM pipeline_runs WHERE source='reddit'")).fetchone()
        assert run is not None
        assert run.status == 'failed'
        errors = run.errors
        assert len(errors) == 1
        assert "Custom source exception" in errors[0]
