import asyncio
import time
from openai import AsyncOpenAI
import settings

client = AsyncOpenAI(
    api_key=settings.API_KEY,
    base_url=settings.BASE_URL
)

async def main():
    t0 = time.perf_counter()
    first = None
    stream = await client.chat.completions.create(
        model=settings.MODEL,
        messages=[{"role": "user",
                   "content": "用三句话说明电商退款政策一般包含哪些条款"}],
        stream=True,
    )

    print("回答：", end="", flush=True)
    async for chunk in stream:
        if not chunk.choices:
            continue
        piece = chunk.choices[0].delta.content
        if piece:
            if first is None:
                first = time.perf_counter() - t0
            print(piece, end="", flush=True)

    print()
    print(f"首字延迟 {first:.2f}s / 总耗时 {time.perf_counter() - t0:.2f}s")

asyncio.run(main())