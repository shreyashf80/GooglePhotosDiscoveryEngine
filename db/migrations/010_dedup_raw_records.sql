ALTER TABLE raw_records ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE raw_records ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT FALSE;
ALTER TABLE raw_records ADD COLUMN IF NOT EXISTS passes_keyword_filter BOOLEAN DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_raw_records_content_hash ON raw_records(content_hash);
