"""演示：重启后从 checkpoint 恢复并继续。运行：python -m scripts.resume"""
import asyncio
import sys

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from app.agent.checkpointer import PG_URI
from app.agent.graph import build_graph

THREAD = "order-7666"


async def main():
    async with AsyncPostgresSaver.from_conn_string(PG_URI) as cp:
        app = build_graph(cp)
        cfg = {"configurable": {"thread_id": THREAD}}

        # 先看看这个 thread 现在是什么状态
        st = await app.aget_state(cfg)
        if not st.values:
            print("没有这个 thread 的状态，检查 thread_id 是否一致")
            return

        print("恢复出来的历史消息数：", len(st.values["messages"]))
        print("停在节点：", st.next)
        if st.tasks and st.tasks[0].interrupts:
            print("待审批内容：", st.tasks[0].interrupts[0].value["message"])

        final = await app.ainvoke(Command(resume="yes"), cfg)
        print("继续跑完：", final["messages"][-1].content)


if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
