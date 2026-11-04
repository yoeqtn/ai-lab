import asyncio

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
import sys
from checkpointer import PG_URI
from graph import build_graph

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