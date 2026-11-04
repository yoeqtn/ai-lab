import asyncio
from embedding import embed_texts


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度：1 最像，0 无关，-1 相反"""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb)


async def main():
    texts = [
        "我要退款",
        "7天无理由退货怎么办",
        "今天北京天气怎么样",
    ]
    vecs = await embed_texts(texts)
    print("条数:", len(vecs), "维度:", len(vecs[0]))
    print("退款 vs 退货 :", round(cosine(vecs[0], vecs[1]), 4))
    print("退款 vs 天气 :", round(cosine(vecs[0], vecs[2]), 4))
    print("退货 vs 天气 :", round(cosine(vecs[1], vecs[2]), 4))


asyncio.run(main())