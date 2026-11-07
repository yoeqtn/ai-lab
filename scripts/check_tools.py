"""手动冒烟：直接调工具，确认检索和订单查询可用。运行：python -m scripts.check_tools"""
import asyncio
import sys

from app.agent.tools import get_order_status, search_docs


async def main():
    print("--- 检索")
    print(await search_docs.ainvoke({"query": "退款政策"}))
    print("--- 订单")
    print(get_order_status.invoke({"order_id": "A12345"}))


if __name__ == '__main__':
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
