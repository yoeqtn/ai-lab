import asyncio
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from checkpointer import PG_URI
import sys
async def main():
    async with AsyncPostgresSaver.from_conn_string(PG_URI) as cp:
        await cp.setup()
        print("checkpointer 表已就绪")

if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())