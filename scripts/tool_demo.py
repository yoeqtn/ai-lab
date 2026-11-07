"""手写一遍工具调用循环，看清 function calling 的本质。

运行：python -m scripts.tool_demo
"""
import asyncio
import json

from openai import AsyncOpenAI

from app.agent.tools import get_order_status, search_docs
from app.core import config

client = AsyncOpenAI(
    api_key=config.API_KEY,
    base_url=config.BASE_URL,
)

# 手动写 schema，就是为了让你看见：tools 就是一段 JSON，不是黑魔法。
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "在企业知识库中检索资料片段。用户问公司政策、退换货规则、"
                           "报销流程时使用。查订单不要用这个。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "用户的原始问题"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "查询订单物流状态。用户提到订单号、问货到哪了时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号，如 A12345"}
                },
                "required": ["order_id"],
            },
        },
    },
]

REGISTRY = {"search_docs": search_docs, "get_order_status": get_order_status}


async def main():
    messages = [
        {"role": "system", "content": "你是企业客服助手。回答前必须先查资料，"
                                      "资料里没有就说不知道。"},
        {"role": "user", "content": "我想退货怎么办"},
    ]
    # ---------- 第一轮：模型决定"要干什么" ----------
    resp = await client.chat.completions.create(
        model=config.MODEL,
        messages=messages,
        tools=TOOL_SCHEMAS,
    )
    msg = resp.choices[0].message
    print("模型返回的文字内容：", repr(msg.content))
    print("模型返回的工具调用：", msg.tool_calls)

    if not msg.tool_calls:
        print("模型决定不调工具，直接回答：", msg.content)
        return

    # 把模型的"决定"写回历史，这一条不能漏
    messages.append(msg.model_dump(exclude_none=True))

    # ---------- 执行它要求的每一个调用 ----------
    for tc in msg.tool_calls:
        fn = REGISTRY[tc.function.name]
        args = json.loads(tc.function.arguments)
        print(f"→ 执行 {tc.function.name}({args})")

        result = await fn.ainvoke(args)

        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,      # 必须对上，否则模型不知道谁的结果
            "content": str(result),
        })

    # ---------- 第二轮：模型拿着结果写答案 ----------
    resp2 = await client.chat.completions.create(
        model=config.MODEL,
        messages=messages,
    )
    print("\n=== 最终回答 ===")
    print(resp2.choices[0].message.content)


if __name__ == '__main__':
    asyncio.run(main())
