import asyncio
from backend.services.data import execute_query
async def test():
    data = await execute_query("SELECT * FROM segment_stats LIMIT 5")
    print("segment_stats count:", len(data))
    if data:
        print("First row:", data[0])
asyncio.run(test())
