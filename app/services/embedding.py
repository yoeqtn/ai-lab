import asyncio

from openai import AsyncOpenAI

from app.core import config

client = AsyncOpenAI(
    api_key=config.API_KEY,
    base_url=config.BASE_URL,
    timeout=30.0,
    max_retries=2,
)

# 百炼 text-embedding 系列单次最多 10 条，超了报错
BATCH_SIZE = config.EMBED_BATCH


async def _embed_batch(batch: list[str]) -> list[list[float]]:
    resp = await client.embeddings.create(
        model=config.EMBED_MODEL,
        input=batch,
        dimensions=config.EMBED_DIM,
    )
    # 按 index 排序，别指望返回顺序一定等于输入顺序
    return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """把一批文本变成向量。返回顺序与输入顺序严格一致。

    分批并发（上限 EMBED_CONCURRENCY），避免大文件串行等待几百次网络往返。
    """
    if not texts:
        return []

    batches = [texts[i:i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]
    semaphore = asyncio.Semaphore(max(1, config.EMBED_CONCURRENCY))

    async def run(batch: list[str]) -> list[list[float]]:
        async with semaphore:
            return await _embed_batch(batch)

    results = await asyncio.gather(*(run(b) for b in batches))
    vectors = [vec for batch in results for vec in batch]

    if len(vectors) != len(texts):
        raise RuntimeError(f"向量数量不匹配：{len(vectors)} vs {len(texts)}")
    return vectors


async def embed_one(text: str) -> list[float]:
    """单条文本的快捷方式，检索时用这个。"""
    return (await embed_texts([text]))[0]
