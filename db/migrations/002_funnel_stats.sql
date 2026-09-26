-- Migration 002: Add funnel_stats table for retrieval funnel stages (FR-88)
-- Maps episode failures to the stage where retrieval broke:
--   express, understand, evaluate, refine

CREATE TABLE IF NOT EXISTS funnel_stats (
    stage               TEXT PRIMARY KEY,           -- express, understand, evaluate, refine
    episode_count       INTEGER NOT NULL DEFAULT 0,
    general_complaint_count INTEGER NOT NULL DEFAULT 0,
    gave_up_rate        REAL NOT NULL DEFAULT 0.0,
    avg_severity        REAL NOT NULL DEFAULT 0.0,
    evidence_strength   TEXT NOT NULL DEFAULT 'anecdotal',  -- strong, directional, anecdotal
    details             JSONB,                      -- per-signal breakdown, top failure modes etc.
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
