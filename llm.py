from openai import AsyncOpenAI

import settings

# 全局只建一个 client：内部带连接池，重复创建会浪费资源
client = AsyncOpenAI(
    api_key=settings.API_KEY,
    base_url=settings.BASE_URL,
    timeout=60.0,      # 超时：不设的话网络卡住会一直挂着
    max_retries=2,     # 失败自动重试 2 次（限流、网络抖动）
)

SYSTEM = "你是一个简洁的中文助手，回答不超过三句话。"

async def stream_chat(question: str, system: str = SYSTEM):
    """流式：一段段吐出文字，给接口层用"""
    stream = await client.chat.completions.create(
        model=settings.MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        stream=True,
        temperature=0,
        max_tokens=800,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        piece = chunk.choices[0].delta.content
        if piece:
            yield piece