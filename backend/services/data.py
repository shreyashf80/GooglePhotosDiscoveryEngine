import json
from datetime import datetime
from sqlalchemy import text
from typing import Any, List, Dict

from backend.db import engine

async def execute_query(query: str, params: dict = None) -> List[Dict[str, Any]]:
    from backend.main import query_count
    query_count.set(query_count.get() + 1)
    if not engine:
        return []
    async with engine.begin() as conn:
        result = await conn.execute(text(query), params or {})
        
        if result.returns_rows:
            # result.mappings().all() returns a list of RowMapping objects
            rows = result.mappings().all()
            return [dict(row) for row in rows]
        return []

async def fetch_one(query: str, params: dict = None) -> Dict[str, Any]:
    rows = await execute_query(query, params)
    return rows[0] if rows else None
