import asyncio
from backend.services.data import execute_query
async def test():
    ev = await execute_query("SELECT column_name FROM information_schema.columns WHERE table_name='hypothesis_evidence'")
    print("evidence cols:", [c['column_name'] for c in ev])
    cues = await execute_query("SELECT column_name FROM information_schema.columns WHERE table_name='episode_cues'")
    print("cues cols:", [c['column_name'] for c in cues])
asyncio.run(test())
