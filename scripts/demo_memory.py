"""演示：会话记忆按 thread_id 隔离。运行：python -m scripts.demo_memory"""
import asyncio
import sys

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agent.checkpointer import PG_URI
from app.agent.graph import build_graph


def rough_tokens(messages) -> int:
    """粗估 token：中文按 1 字 ≈ 1.5 token，英文按 4 字符 ≈ 1 token 算。
    只用来观察趋势，别拿它当计费依据。"""
    total = 0
    for m in messages:
        text = str(m.content or "")
        cn = sum(1 for ch in text if "一" <= ch <= "鿿")
        total += int(cn * 1.5) + (len(text) - cn) // 4 + 4
    return total


async def ask(app, thread_id: str, text: str):
    cfg = {"configurable": {"thread_id": thread_id}}
    result = await app.ainvoke({"messages": [HumanMessage(content=text)]}, cfg)
    msgs = result["messages"]
    print(f"消息数={len(msgs)} 估算token={rough_tokens(msgs)}")
    print(f"    答：{str(msgs[-1].content)[:60]}")


async def main():
    async with AsyncPostgresSaver.from_conn_string(PG_URI) as cp:
        await cp.setup()
        app = build_graph(cp)
        await ask(app, "user-1", "我叫小王，我的订单号是 A12345")
        await ask(app, "user-1", "我刚才说的订单号是多少？")
        print("---- 换一个人 ----")
        await ask(app, "user-2", "我刚才说的订单号是多少？")


if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
