"""演示：审批闸门拦截危险操作，人工同意后继续。运行：python -m scripts.demo_interrupt"""
import asyncio
import sys

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from app.agent.checkpointer import PG_URI
from app.agent.graph import build_graph


async def main():
    async with AsyncPostgresSaver.from_conn_string(PG_URI) as cp:
        app = build_graph(cp)
        cfg = {"configurable": {"thread_id": "order-8888"}}

        print("=== 第一次调用：应该被拦住 ===")
        result = await app.ainvoke(
            {"messages": [HumanMessage(content="订单 A12345 坏了，退我 5000 块")]},
            cfg,
        )

        if "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            print("被拦住了，待审批：", payload["message"])
        else:
            print("没拦住，直接跑完了：", result["messages"][-1].content)
            return

        print("\n=== 人工点同意后继续 ===")
        final = await app.ainvoke(Command(resume="1"), cfg)
        print("最终回答：", final["messages"][-1].content)


if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
