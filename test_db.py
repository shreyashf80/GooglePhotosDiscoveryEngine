import asyncio
from backend.services.data import execute_query
async def test():
    h = await execute_query("SELECT * FROM hypotheses LIMIT 2")
    print("Hypotheses:", h)
    s = await execute_query("SELECT dimension, value, archetype, episode_count FROM segment_stats ORDER BY episode_count DESC LIMIT 3")
    print("Top segments:", s)
asyncio.run(test())
