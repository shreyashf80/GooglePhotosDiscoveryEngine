DROP TABLE IF EXISTS literature_chunks CASCADE;
DROP TABLE IF EXISTS literature_sources CASCADE;

CREATE TABLE literature_sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    citation TEXT,
    link TEXT,
    era TEXT,
    tags TEXT[]
);

CREATE TABLE literature_chunks (
    source_id TEXT PRIMARY KEY REFERENCES literature_sources(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    embedding halfvec(384)
);

CREATE INDEX idx_literature_chunks_embedding ON literature_chunks USING hnsw (embedding halfvec_cosine_ops);
