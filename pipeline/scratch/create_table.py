import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])
with engine.begin() as conn:
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS funnel_stats (
        stage               TEXT PRIMARY KEY,
        episode_count       INTEGER NOT NULL DEFAULT 0,
        general_complaint_count INTEGER NOT NULL DEFAULT 0,
        gave_up_rate        REAL NOT NULL DEFAULT 0.0,
        avg_severity        REAL NOT NULL DEFAULT 0.0,
        evidence_strength   TEXT NOT NULL DEFAULT 'anecdotal',
        details             JSONB,
        computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """))
