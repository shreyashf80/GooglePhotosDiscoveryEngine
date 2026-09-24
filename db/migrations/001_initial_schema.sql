-- Migration 001: Enable pgvector and create core tables
-- References: architecture.md Section 4, DR-4, FR-61

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- pipeline_runs (must be created first — raw_records references it)
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id      TEXT PRIMARY KEY,
    stage       TEXT NOT NULL,
    source      TEXT,
    started_at  TIMESTAMPTZ NOT NULL,
    ended_at    TIMESTAMPTZ,
    counts      JSONB,
    errors      JSONB,
    tokens      JSONB,
    status      TEXT DEFAULT 'running'
);

-- ============================================================
-- raw_records
-- ============================================================

CREATE TABLE IF NOT EXISTS raw_records (
    record_id               TEXT PRIMARY KEY,
    source                  TEXT NOT NULL,
    item_type               TEXT NOT NULL,
    product                 TEXT NOT NULL DEFAULT 'google_photos',
    url                     TEXT,
    author_hash             TEXT,
    created_at              TIMESTAMPTZ,
    lang                    TEXT,
    text                    TEXT,
    text_len                INTEGER,
    truncated               BOOLEAN DEFAULT FALSE,
    keyword_hit             BOOLEAN,
    relevance_class         TEXT,
    relevance_reason        TEXT,
    general_failure_modes   TEXT[],
    platform                TEXT,
    mentions_ask_photos     BOOLEAN,
    ask_photos_note         TEXT,
    status                  TEXT NOT NULL DEFAULT 'raw',
    retry_count             INTEGER DEFAULT 0,
    last_error              TEXT,
    extra                   JSONB,
    ingested_at             TIMESTAMPTZ DEFAULT NOW(),
    run_id                  TEXT REFERENCES pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_records_status ON raw_records(status);
CREATE INDEX IF NOT EXISTS idx_raw_records_source ON raw_records(source);
CREATE INDEX IF NOT EXISTS idx_raw_records_created ON raw_records(created_at);

-- ============================================================
-- episodes
-- ============================================================

CREATE TABLE IF NOT EXISTS episodes (
    episode_id              TEXT PRIMARY KEY,
    record_id               TEXT NOT NULL REFERENCES raw_records(record_id),
    episode_no              SMALLINT NOT NULL,
    target_description      TEXT NOT NULL,
    photo_category          TEXT NOT NULL,
    photo_origin            TEXT NOT NULL,
    photo_age_bucket        TEXT,
    photo_age_evidence      TEXT,
    failure_modes           TEXT[] NOT NULL DEFAULT '{}',
    workarounds             TEXT[] NOT NULL DEFAULT '{}',
    outcome                 TEXT NOT NULL,
    stakes                  TEXT NOT NULL,
    role_hints              TEXT[] DEFAULT '{}',
    archetype_primary       TEXT NOT NULL,
    archetype_secondary     TEXT,
    emergent_label          TEXT,
    summary_en              TEXT NOT NULL,
    quote_original          TEXT NOT NULL,
    quote_en                TEXT NOT NULL,
    extraction_confidence   TEXT NOT NULL,
    prompt_version          TEXT NOT NULL,
    model_id                TEXT NOT NULL,
    embedding               halfvec(384),
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_episodes_record ON episodes(record_id);
CREATE INDEX IF NOT EXISTS idx_episodes_archetype ON episodes(archetype_primary);
CREATE INDEX IF NOT EXISTS idx_episodes_category ON episodes(photo_category);
CREATE INDEX IF NOT EXISTS idx_episodes_outcome ON episodes(outcome);

-- HNSW index for cosine similarity search (FR-61)
CREATE INDEX IF NOT EXISTS idx_episodes_embedding ON episodes
    USING hnsw (embedding halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================
-- episode_cues (FR-44)
-- ============================================================

CREATE TABLE IF NOT EXISTS episode_cues (
    id          SERIAL PRIMARY KEY,
    episode_id  TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
    cue_type    TEXT NOT NULL,
    value       TEXT NOT NULL,
    precision   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_episode_cues_episode ON episode_cues(episode_id);
CREATE INDEX IF NOT EXISTS idx_episode_cues_type ON episode_cues(cue_type);

-- ============================================================
-- episode_forgotten (FR-44)
-- ============================================================

CREATE TABLE IF NOT EXISTS episode_forgotten (
    id          SERIAL PRIMARY KEY,
    episode_id  TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
    cue_type    TEXT NOT NULL,
    evidence    TEXT NOT NULL
);

-- ============================================================
-- episode_queries (FR-44)
-- ============================================================

CREATE TABLE IF NOT EXISTS episode_queries (
    id          SERIAL PRIMARY KEY,
    episode_id  TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
    query_text  TEXT NOT NULL,
    query_style TEXT NOT NULL,
    position    SMALLINT NOT NULL
);

-- ============================================================
-- hypotheses (FR-71 – FR-75)
-- ============================================================

CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id   TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    statement       TEXT NOT NULL,
    status          TEXT NOT NULL,
    support_count   INTEGER NOT NULL DEFAULT 0,
    contradict_count INTEGER NOT NULL DEFAULT 0,
    relevant_count  INTEGER NOT NULL DEFAULT 0,
    evidence_strength TEXT NOT NULL,
    details         JSONB,
    computed_at     TIMESTAMPTZ NOT NULL
);

-- ============================================================
-- hypothesis_evidence (FR-75)
-- ============================================================

CREATE TABLE IF NOT EXISTS hypothesis_evidence (
    hypothesis_id TEXT NOT NULL REFERENCES hypotheses(hypothesis_id),
    episode_id    TEXT NOT NULL REFERENCES episodes(episode_id),
    direction     TEXT NOT NULL,
    rank          SMALLINT,
    PRIMARY KEY (hypothesis_id, episode_id)
);

-- ============================================================
-- archetype_stats (FR-80 – FR-83)
-- ============================================================

CREATE TABLE IF NOT EXISTS archetype_stats (
    archetype           TEXT PRIMARY KEY,
    episode_count       INTEGER NOT NULL,
    share_of_episodes   REAL NOT NULL,
    outcome_distribution JSONB NOT NULL,
    top_cue_types       JSONB NOT NULL,
    top_failure_modes   JSONB NOT NULL,
    top_workarounds     JSONB NOT NULL,
    source_mix          JSONB NOT NULL,
    language_mix        JSONB NOT NULL,
    category_mix        JSONB NOT NULL,
    avg_severity        REAL NOT NULL,
    avg_stakes_weight   REAL NOT NULL,
    opportunity_score   REAL NOT NULL,
    evidence_strength   TEXT NOT NULL,
    computed_at         TIMESTAMPTZ NOT NULL
);

-- ============================================================
-- cue_stats (FR-85 – FR-87)
-- ============================================================

CREATE TABLE IF NOT EXISTS cue_stats (
    cue_type            TEXT PRIMARY KEY,
    remembered_share    REAL NOT NULL,
    precision_exact     REAL NOT NULL,
    precision_approximate REAL NOT NULL,
    precision_vague     REAL NOT NULL,
    forgotten_count     INTEGER NOT NULL,
    failure_rate        REAL NOT NULL,
    gap_score           REAL,
    computed_at         TIMESTAMPTZ NOT NULL
);

-- ============================================================
-- capability_reference (FR-86)
-- ============================================================

CREATE TABLE IF NOT EXISTS capability_reference (
    cue_type        TEXT PRIMARY KEY,
    searchable      TEXT NOT NULL,
    note            TEXT,
    verified_how    TEXT,
    verified_at     TIMESTAMPTZ
);

-- ============================================================
-- Supporting tables
-- ============================================================

CREATE TABLE IF NOT EXISTS segment_stats (
    dimension       TEXT NOT NULL,
    value           TEXT NOT NULL,
    archetype       TEXT NOT NULL,
    episode_count   INTEGER NOT NULL,
    outcome_mix     JSONB NOT NULL,
    PRIMARY KEY (dimension, value, archetype)
);

CREATE TABLE IF NOT EXISTS research_handoff (
    hypothesis_id       TEXT PRIMARY KEY REFERENCES hypotheses(hypothesis_id),
    interview_questions JSONB NOT NULL,
    task_ideas          JSONB NOT NULL,
    screener            JSONB NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL,
    model_id            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS literature_sources (
    source_id   TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    authors     TEXT,
    year        INTEGER,
    url         TEXT,
    imported_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS literature_chunks (
    chunk_id    TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL REFERENCES literature_sources(source_id),
    chunk_text  TEXT NOT NULL,
    embedding   halfvec(384),
    position    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lit_chunks_embedding ON literature_chunks
    USING hnsw (embedding halfvec_cosine_ops);

CREATE TABLE IF NOT EXISTS chat_cache (
    question_hash TEXT PRIMARY KEY,
    response      JSONB NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS eval_results (
    run_at      TIMESTAMPTZ PRIMARY KEY,
    metrics     JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS emergent_labels (
    label           TEXT PRIMARY KEY,
    episode_count   INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending',
    merged_into     TEXT
);
