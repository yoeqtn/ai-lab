import asyncio
import random

from sqlalchemy import select

from db import SessionLocal, engine
from models import Chunk, Document

DIM = 1024


def fake_vec(seed: int) -> list[float]:  # 假向量，D5 换成真 embedding
    rnd = random.Random(seed)
    return [rnd.uniform(-1, 1) for _ in range(DIM)]


def near_vec(base, k=0.3, seed=7):  # 在 base 附近抖一下：模拟"意思相近"
    rnd = random.Random(seed)
    return [x + k * rnd.uniform(-1, 1) for x in base]


async def main():
    query = fake_vec(0)  # 假装这是"用户提问"算出来的向量

    async with SessionLocal() as s:
        doc = Document(tenant_id="demo", filename="退款政策.pdf")
        s.add(doc)
        await s.flush()  # 拿到 doc.id，还没提交

        s.add_all([
            Chunk(document_id=doc.id, chunk_index=0, embedding=near_vec(query),
                  content="签收后 7 天内可无理由退款，需保持包装完整。"),
            Chunk(document_id=doc.id, chunk_index=1, embedding=fake_vec(1),
                  content="发票抬头请填写公司全称，开票周期为 3 个工作日。"),
            Chunk(document_id=doc.id, chunk_index=2, embedding=fake_vec(2),
                  content="会员积分每消费 1 元累计 1 分，积分年底清零。"),
        ])
        await s.commit()

        distance = Chunk.embedding.cosine_distance(query).label("distance")
        rows = (await s.execute(select(Chunk.content, distance)
                                .order_by(distance).limit(3))).all()
        for content, d in rows:
            print(f"距离 {d:.4f}  {content}")

    await engine.dispose()


asyncio.run(main())