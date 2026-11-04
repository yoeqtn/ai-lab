import asyncio
from sqlalchemy import select
from db import SessionLocal, engine
from models import Chunk
from embedding import embed_one


async def search_chunks(query: str, top_k: int = 3):
    """返回 [(content, distance), ...]，distance 越小越相关"""
    q_vec = await embed_one(query)

    # cosine_distance 就是 SQL 里的 <=> 运算符
    dist = Chunk.embedding.cosine_distance(q_vec)

    stmt = (
        select(Chunk.content,
        dist.label("distance")).order_by(dist).limit(top_k)
    )

    async with SessionLocal() as s:
        rows = (await s.execute(stmt)).all()
    return rows


async def main():
    for q in ["我想退货怎么办", "退款多久能到账", "你们支持花呗吗"]:
        print(f"\n=== 问题：{q} ===")
        rows = await search_chunks(q, top_k=3)
        for content, d in rows:
            print(f"  距离 {d:.4f} | {content[:36]}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())