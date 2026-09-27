-- Migration 003: V2 Schema Updates

ALTER TABLE raw_records
ADD COLUMN IF NOT EXISTS out_of_scope BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS out_of_scope_reason TEXT,
ADD COLUMN IF NOT EXISTS record_behavior JSONB;

ALTER TABLE episodes
ADD COLUMN IF NOT EXISTS trigger TEXT,
ADD COLUMN IF NOT EXISTS expectation TEXT,
ADD COLUMN IF NOT EXISTS mental_model TEXT,
ADD COLUMN IF NOT EXISTS organizing_habit TEXT,
ADD COLUMN IF NOT EXISTS frequency TEXT,
ADD COLUMN IF NOT EXISTS emotional_cost TEXT,
ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT FALSE;

-- Update enum check for RelevanceClass if we used constraints, but we just use TEXT.
