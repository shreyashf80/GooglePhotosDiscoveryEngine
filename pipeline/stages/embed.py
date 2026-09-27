"""
Embed stage — embed episode summaries using fastembed BGE-small-en-v1.5.

References:
  FR-60 — Only summary_en is embedded
  FR-61 — Stored as halfvec(384) with HNSW index
"""

import logging
from fastembed import TextEmbedding

from pipeline.db import engine
from pipeline.config import EMBED_BATCH_SIZE
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Lazy-loaded singleton
_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        logger.info("Loading fastembed model BAAI/bge-small-en-v1.5...")
        _model = TextEmbedding("BAAI/bge-small-en-v1.5")
        logger.info("Model loaded.")
    return _model


def run_embed() -> dict:
    """Embed summary_en for all episodes that don't have embeddings yet.

    Returns counts dict.
    """
    model = _get_model()

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT episode_id, summary_en FROM episodes WHERE embedding IS NULL"
        )).fetchall()

    if not rows:
        logger.info("Embed: no episodes to embed")
        return {"processed": 0}

    logger.info(f"Embed: {len(rows)} episodes to embed")
    processed = 0

    for i in range(0, len(rows), EMBED_BATCH_SIZE):
        batch = rows[i:i + EMBED_BATCH_SIZE]
        texts = [r.summary_en for r in batch]
        ids = [r.episode_id for r in batch]

        # fastembed returns a generator; materialise it
        embeddings = list(model.embed(texts))

        with engine.begin() as conn:
            for eid, emb in zip(ids, embeddings):
                vec_str = "[" + ",".join(str(float(v)) for v in emb) + "]"
                conn.execute(
                    text("UPDATE episodes SET embedding = :vec WHERE episode_id = :eid"),
                    {"vec": vec_str, "eid": eid},
                )

        processed += len(batch)
        logger.info(f"Embed batch {i}-{i + len(batch)}: {len(batch)} embedded")

    # Update status to 'embedded' for records whose episodes are now all embedded
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE raw_records r SET status = 'embedded'
            WHERE r.status = 'extracted'
              AND NOT EXISTS (
                SELECT 1 FROM episodes e
                WHERE e.record_id = r.record_id AND e.embedding IS NULL
              )
        """))

    # Cross-record duplicates (FR-X)
    logger.info("Embed: flagging cross-record duplicates...")
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE episodes e1
            SET is_duplicate = TRUE
            FROM raw_records r1
            WHERE e1.record_id = r1.record_id
              AND EXISTS (
                SELECT 1 FROM episodes e2
                JOIN raw_records r2 ON e2.record_id = r2.record_id
                WHERE e1.episode_id != e2.episode_id
                  AND e1.embedding IS NOT NULL AND e2.embedding IS NOT NULL
                  AND (
                      (r1.author_hash = r2.author_hash AND r1.author_hash IS NOT NULL)
                      OR
                      (r1.source = 'reddit' AND r2.source = 'reddit' 
                       AND substring(r1.url from 'comments/([^/]+)') = substring(r2.url from 'comments/([^/]+)') 
                       AND substring(r1.url from 'comments/([^/]+)') IS NOT NULL)
                  )
                  AND (e1.embedding <=> e2.embedding) < 0.08
                  AND (r1.created_at > r2.created_at OR (r1.created_at = r2.created_at AND e1.episode_id > e2.episode_id))
            )
        """))

    logger.info(f"Embed stage complete: {processed} episodes embedded")
    return {"processed": processed}
