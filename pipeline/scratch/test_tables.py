import asyncio
from backend.services.data import execute_query
async def test():
    schema = await execute_query("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    print("Tables:", [t['table_name'] for t in schema])
    # check hypotheses schema
    h = await execute_query("SELECT column_name FROM information_schema.columns WHERE table_name='hypotheses'")
    print("hypotheses cols:", [c['column_name'] for c in h])
asyncio.run(test())
