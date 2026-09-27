import asyncio
from backend.services.data import execute_query
async def test():
    res = await execute_query("SELECT distinct dimension FROM segment_stats")
    print([r['dimension'] for r in res])
asyncio.run(test())
