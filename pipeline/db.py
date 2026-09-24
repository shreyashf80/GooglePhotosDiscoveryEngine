"""
Pipeline database helpers — sync SQLAlchemy engine and session factory.
Reads DATABASE_URL from pipeline config.

Note: This uses psycopg2 (sync) for the pipeline CLI.
"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from pipeline.config import DATABASE_URL

logger = logging.getLogger(__name__)


def _normalize_db_url(url: str) -> str:
    """Normalize postgres:// to postgresql:// for SQLAlchemy."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


# Create sync engine for pipeline use
engine = create_engine(
    _normalize_db_url(DATABASE_URL),
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine)


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()


def execute_sql(sql: str, params: dict | None = None) -> list[dict]:
    """Execute raw SQL and return results as list of dicts with error handling."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            if result.returns_rows:
                columns = list(result.keys())
                return [dict(zip(columns, row)) for row in result.fetchall()]
            conn.commit()
            return []
    except Exception as e:
        logger.error("Database query failed (%s)", type(e).__name__)
        raise RuntimeError(f"Database query failed: {type(e).__name__}") from e


def get_db_size_bytes() -> int:
    """Get current database size in bytes via pg_database_size (DR-5)."""
    try:
        rows = execute_sql("SELECT pg_database_size(current_database()) AS size")
        return rows[0]["size"] if rows else 0
    except Exception as e:
        logger.warning("Failed to get database size (%s)", type(e).__name__)
        return 0
