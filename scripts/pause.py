import asyncio
import sys
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from checkpointer import PG_URI
from graph import build_graph

THREAD = "order-7666"


async def main():

    async with AsyncPostgresSaver.from_conn_string(PG_URI) as cp:
        app = build_graph(cp)
        cfg = {"configurable": {"thread_id": THREAD}}
        r = await app.ainvoke(
            {"messages": [HumanMessage(content="订单 A12345 退我 2000 元")]}, cfg
        )
        print("状态：", "待审批" if "__interrupt__" in r else "已完成")
        print("请记下 thread_id =", THREAD)
        print("现在按红色方块【停止】，或者直接关掉 PyCharm")


if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())