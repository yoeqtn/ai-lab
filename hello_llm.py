import asyncio
from openai import AsyncOpenAI
import settings

client = AsyncOpenAI(
    api_key=settings.API_KEY,
    base_url=settings.BASE_URL
)

async def main():
    resp = await client.chat.completions.create(
        model=settings.MODEL,
        messages=[{"role": "user", "content": "用两句话解释什么是 RAG"}],
    )
    print(resp.choices[0].message.content)
    print("--- 用量 ---")
    print("输入 tokens:", resp.usage.prompt_tokens)
    print("输出 tokens:", resp.usage.completion_tokens)

asyncio.run(main())