import asyncio
from tools import search_docs, get_order_status

async def main():
    print("--- 检索")
    print(await search_docs.ainvoke({"query": "退款政策"}))
    print("--- 订单")
    print(get_order_status.invoke({"order_id": "A12345"}))

asyncio.run(main())