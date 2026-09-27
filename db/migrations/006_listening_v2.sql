-- Migration 006: Listening V2 Schema Updates

ALTER TABLE raw_records ADD COLUMN IF NOT EXISTS scope TEXT;

CREATE TABLE IF NOT EXISTS themes (
    id TEXT PRIMARY KEY,
    scope TEXT,
    name TEXT,
    description TEXT,
    signals INTEGER,
    distinct_authors INTEGER,
    sources_count INTEGER,
    severe_share REAL,
    rank_score REAL,
    evidence_strength TEXT,
    mixes JSONB,
    quotes JSONB
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY,
    record_id TEXT,
    summary_en TEXT,
    is_success BOOLEAN,
    outcome TEXT,
    emotional_cost TEXT,
    frequency TEXT,
    product TEXT,
    platform TEXT,
    mentions_ask_photos BOOLEAN,
    quote_original TEXT,
    quote_en TEXT,
    embedding halfvec(384),
    is_duplicate BOOLEAN,
    prompt_version TEXT,
    model_id TEXT
);

CREATE TABLE IF NOT EXISTS signal_reasons (
    id SERIAL PRIMARY KEY,
    signal_id TEXT,
    text TEXT,
    funnel_stage TEXT,
    specificity TEXT,
    embedding halfvec(384),
    theme_id TEXT
);

ALTER TABLE hypotheses
ADD COLUMN IF NOT EXISTS origin TEXT,
ADD COLUMN IF NOT EXISTS theme_id TEXT,
ADD COLUMN IF NOT EXISTS rank REAL,
ADD COLUMN IF NOT EXISTS research_question TEXT;

UPDATE hypotheses SET origin = 'prior' WHERE origin IS NULL;
