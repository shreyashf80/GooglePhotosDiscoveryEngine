import os
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from pipeline.db import engine
from pipeline.stages.filter import run_filter
from pipeline.stages.extract import run_extract
from pipeline.cli import trim, export_sample
from shared.models import RecordExtraction, EpisodeExtraction
from shared.enums import RelevanceClass, FailureMode, Outcome


def test_trim(clean_db):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO raw_records (record_id, source, item_type, text, status)
            VALUES 
            ('r1', 'reddit', 'post', 'some text 1', 'excluded'),
            ('r2', 'reddit', 'post', 'some text 2', 'filtered'),
            ('r3', 'reddit', 'post', 'some text 3', 'excluded')
        """))
    
    trim()
    
    with engine.begin() as conn:
        res = conn.execute(text("SELECT record_id, text FROM raw_records ORDER BY record_id")).fetchall()
        
    assert res[0].text is None  # r1 excluded
    assert res[1].text == 'some text 2'  # r2 filtered, not trimmed
    assert res[2].text is None  # r3 excluded


def test_export_sample(clean_db, tmp_path):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO raw_records (record_id, source, item_type, text, status)
            VALUES ('r1', 'reddit', 'post', 'test text', 'extracted')
        """))
        conn.execute(text("""
            INSERT INTO episodes (
                episode_id, record_id, episode_no, target_description, photo_category, 
                photo_origin, outcome, stakes, archetype_primary, summary_en, quote_original, quote_en, 
                extraction_confidence, prompt_version, model_id
            ) VALUES (
                'e1', 'r1', 1, 'target', 'receipt', 'camera', 'success', 'low', 'utility', 
                'summary', 'orig', 'en', 'high', 'v1', 'test_model'
            )
        """))
    
    out_file = tmp_path / "sample.csv"
    export_sample(output=str(out_file), limit=10)
    
    assert out_file.exists()
    content = out_file.read_text()
    assert "e1" in content
    assert "test text" in content


@patch("pipeline.stages.filter.GeminiClient.generate")
def test_run_filter_integration(mock_generate, clean_db):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO raw_records (record_id, source, item_type, text, status, lang)
            VALUES 
            ('r1', 'reddit', 'post', 'find my photo', 'deduped', 'en'),
            ('r2', 'reddit', 'post', 'irrelevant garbage without keywords', 'deduped', 'en')
        """))

    mock_generate.return_value = {
        "results": [
            {
                "record_id": "r1", 
                "source": "reddit",
                "lang": "en", 
                "text": "find my photo",
                "relevance_class": "specific_episode"
            }
        ]
    }
    
    counts = run_filter()
    assert counts["processed"] == 2
    assert counts["keyword_hit"] == 1
    assert counts["keyword_miss_en_excluded"] == 1
    
    with engine.begin() as conn:
        res = conn.execute(text("SELECT record_id, status FROM raw_records ORDER BY record_id")).fetchall()
        statuses = {r.record_id: r.status for r in res}
        assert statuses["r1"] == "filtered"
        assert statuses["r2"] == "excluded"
        
        # Check pipeline_runs
        run_res = conn.execute(text("SELECT * FROM pipeline_runs WHERE stage='filter'")).fetchone()
        assert run_res is not None
        assert run_res.status == 'completed'
        assert run_res.tokens is not None


@patch("pipeline.stages.extract.GeminiClient.generate")
def test_run_extract_integration(mock_generate, clean_db):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO raw_records (record_id, source, item_type, text, status)
            VALUES ('r1', 'reddit', 'post', 'find my photo', 'filtered')
        """))

    mock_generate.return_value = {
        "record_id": "r1",
        "product": "google_photos",
        "platform": "ios",
        "mentions_ask_photos": False,
        "general_failure_modes": [],
        "episodes": [{
            "target_description": "desc",
            "photo_category": "screenshot_digital",
            "photo_origin": "own_camera",
            "photo_age_bucket": "unknown",
            "cues_remembered": [],
            "cues_forgotten": [],
            "queries_tried": [],
            "failure_modes": [],
            "workarounds": [],
            "outcome": "gave_up",
            "stakes": "unknown",
            "role_hints": [],
            "archetype_primary": "utility_lookup",
            "summary_en": "summary",
            "quote_original": "orig",
            "quote_en": "en",
            "extraction_confidence": "high"
        }]
    }
    
    counts = run_extract()
    assert counts["records_processed"] == 1
    assert counts["records_extracted"] == 1
    assert counts["episodes_created"] == 1
    
    with engine.begin() as conn:
        r_status = conn.execute(text("SELECT status FROM raw_records WHERE record_id='r1'")).scalar()
        assert r_status == 'extracted'
        
        ep_count = conn.execute(text("SELECT count(*) FROM episodes WHERE record_id='r1'")).scalar()
        assert ep_count == 1
        
        # Check pipeline_runs
        run_res = conn.execute(text("SELECT * FROM pipeline_runs WHERE stage='extract'")).fetchone()
        assert run_res is not None
        assert run_res.status == 'completed'
        assert run_res.tokens is not None


@patch("pipeline.stages.extract.GeminiClient.generate")
def test_extract_retry_threshold(mock_generate, clean_db):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO raw_records (record_id, source, item_type, text, status, retry_count)
            VALUES 
            ('r1', 'reddit', 'post', 'fail1', 'filtered', 0)
        """))

    # Mock an error 
    mock_generate.side_effect = Exception("simulated API error")
    
    # 1st run -> failure, retry_count becomes 1
    run_extract()
    with engine.begin() as conn:
        r = conn.execute(text("SELECT status, retry_count FROM raw_records WHERE record_id='r1'")).fetchone()
        assert r.status == 'filtered'
        assert r.retry_count == 1
        
    # 2nd run -> failure, retry_count becomes 2
    run_extract()
    with engine.begin() as conn:
        r = conn.execute(text("SELECT status, retry_count FROM raw_records WHERE record_id='r1'")).fetchone()
        assert r.status == 'filtered'
        assert r.retry_count == 2
        
    # 3rd run -> failure, retry_count becomes 3, threshold reached -> extract_failed
    run_extract()
    with engine.begin() as conn:
        r = conn.execute(text("SELECT status, retry_count FROM raw_records WHERE record_id='r1'")).fetchone()
        assert r.status == 'extract_failed'
        assert r.retry_count == 3
