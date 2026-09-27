-- Migration 005: Create chat_cache table if not exists (FR-106)
-- The architecture already defines this table, so it may already exist.
-- This migration is idempotent.

CREATE TABLE IF NOT EXISTS chat_cache (
    question_hash TEXT PRIMARY KEY,
    response      JSONB NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
