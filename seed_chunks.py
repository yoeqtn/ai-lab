import asyncio
from sqlalchemy import delete
from db import SessionLocal, engine
from models import Document, Chunk
from embedding import embed_texts

DOCS = [
    "本店支持 7 天无理由退货。自签收之日起 7 个自然日内，商品未使用、吊牌完整、包装完好，可申请无理由退货，来回运费由买家承担。",
    "退款将在商家确认收货后 1-3 个工作日内原路退回，具体到账时间以银行或支付平台为准。",
    "生鲜食品、定制商品、贴身衣物、已拆封的软件类商品不支持 7 天无理由退货。",
    "商品出现质量问题（破损、缺件、功能故障），运费由商家承担，买家可在订单页上传照片申请售后。",
    "发票需在订单完成后 30 天内申请，支持电子发票，抬头可为个人或公司。",
    "会员积分在退款成功后会按实际支付金额比例扣回，已使用的优惠券不予返还。",
]


async def main():
    async with SessionLocal() as s:
        # 先清空，保证反复跑不会重复插入
        await s.execute(delete(Chunk))
        await s.execute(delete(Document))
        await s.commit()

        doc = Document(tenant_id="demo", filename="退款政策.md")
        s.add(doc)
        await s.commit()
        await s.refresh(doc)
        print("文档 id:", doc.id)

        vectors = await embed_texts(DOCS)
        print("向量条数:", len(vectors), "维度:", len(vectors[0]))

        for i, (text, vec) in enumerate(zip(DOCS, vectors)):
            s.add(Chunk(
                document_id=doc.id,
                chunk_index=i,
                content=text,
                embedding=vec,
            ))
        await s.commit()
        print(f"写入 {len(DOCS)} 条 chunk 完成")

    await engine.dispose()


asyncio.run(main())