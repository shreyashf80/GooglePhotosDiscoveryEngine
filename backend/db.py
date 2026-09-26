"""
Backend database helpers — async connection pool using asyncpg.
Reads DATABASE_URL from environment.

Per user requirement: if using asyncpg with pooled URL, disable prepared
statement caching by setting statement_cache_size=0.
"""

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

def _normalize_async_db_url(url: str) -> str:
    """Convert postgres:// or postgresql:// to postgresql+asyncpg:// for SQLAlchemy async."""
    if not url:
        return ""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
    if "?" in url:
        # asyncpg doesn't support sslmode query param in the URL through SQLAlchemy
        url = url.split("?")[0]
        
    return url


_database_url = os.environ.get("DATABASE_URL", "")
_async_url = _normalize_async_db_url(_database_url)

if _async_url:
    engine = create_async_engine(
        _async_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0, "ssl": "require"},
    )
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
else:
    engine = None
    AsyncSessionLocal = None


async def get_async_session() -> AsyncSession:
    """Get a new async database session."""
    if AsyncSessionLocal is None:
        raise RuntimeError("DATABASE_URL is not set; cannot create async database session")
    return AsyncSessionLocal()
