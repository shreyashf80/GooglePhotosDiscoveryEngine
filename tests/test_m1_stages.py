import pytest
import uuid
import hashlib
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

from pipeline.stages.dedup import run_dedup

from pipeline.db import engine

def test_run_dedup(clean_db):
    with engine.begin() as conn:
        # 1. Existing non-raw record (should be used for dedup checking)
        conn.execute(text("""
            INSERT INTO raw_records (record_id, source, item_type, text, status) 
            VALUES ('existing_1', 'reddit', 'post', 'This is a unique text.', 'deduped')
        """))
        
        # 2. Raw record that is a duplicate of existing_1
        conn.execute(text("""
            INSERT INTO raw_records (record_id, source, item_type, text, status) 
            VALUES ('raw_dup', 'reddit', 'post', 'This is a unique text.', 'raw')
        """))
        
        # 3. Raw record that is too short
        conn.execute(text("""
            INSERT INTO raw_records (record_id, source, item_type, text, status) 
            VALUES ('raw_short', 'reddit', 'post', 'Too short', 'raw')
        """))
        
        # 4. Raw record that is unique and valid
        conn.execute(text("""
            INSERT INTO raw_records (record_id, source, item_type, text, status) 
            VALUES ('raw_valid', 'reddit', 'post', 'This is a completely new valid text that should survive dedup.', 'raw')
        """))
        
    counts = run_dedup()
    
    assert counts["processed"] == 3
    assert counts["excluded_too_short"] == 1
    assert counts["duplicates_dropped"] == 1
    assert counts["deduped_survivors"] == 1
    
    with engine.begin() as conn:
        # Check duplicate
        dup = conn.execute(text("SELECT status, relevance_reason, text FROM raw_records WHERE record_id='raw_dup'")).fetchone()
        assert dup.status == 'excluded'
        assert dup.relevance_reason == 'duplicate'
        assert dup.text is not None  # Text shouldn't be null
        
        # Check short
        short = conn.execute(text("SELECT status, relevance_reason, text FROM raw_records WHERE record_id='raw_short'")).fetchone()
        assert short.status == 'excluded'
        assert short.relevance_reason == 'too_short'
        assert short.text is not None # Text shouldn't be null
        
        # Check valid
        valid = conn.execute(text("SELECT status, text_len FROM raw_records WHERE record_id='raw_valid'")).fetchone()
        assert valid.status == 'deduped'
        assert valid.text_len > 0
