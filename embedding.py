from openai import AsyncOpenAI
import settings

client = AsyncOpenAI(
    api_key=settings.API_KEY,
    base_url=settings.BASE_URL,
    timeout=30.0,
    max_retries=2,
)

BATCH_SIZE = 10   # 百炼 text-embedding-v3 单次最多 10 条，超了报错


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """把一批文本变成向量。返回顺序与输入顺序严格一致。"""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        resp = await client.embeddings.create(
            model=settings.EMBED_MODEL,
            input=batch,
            dimensions=1024,
        )
        # 按 index 排序，别指望返回顺序一定等于输入顺序
        items = sorted(resp.data, key=lambda d: d.index)
        vectors.extend(d.embedding for d in items)
    return vectors


async def embed_one(text: str) -> list[float]:
    """单条文本的快捷方式，检索时用这个。"""
    return (await embed_texts([text]))[0]