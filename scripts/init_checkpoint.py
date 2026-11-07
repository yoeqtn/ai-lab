"""初始化 LangGraph checkpointer 表。运行：python -m scripts.init_checkpoint"""
import asyncio
import sys

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agent.checkpointer import PG_URI


async def main():
    async with AsyncPostgresSaver.from_conn_string(PG_URI) as cp:
        await cp.setup()
        print("checkpointer 表已就绪")


if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
