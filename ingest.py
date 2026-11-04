from sqlalchemy import delete, select
from db import SessionLocal
from models import Document, Chunk
from chunking import split_text
from embedding import embed_texts

async def ingest_text(filename: str, text: str, tenant_id: str = "demo"):
    """把一段文本变成可检索的知识：切块 → 向量化 → 入库。
    返回 (document_id, chunk 数量)。同名文件会覆盖旧数据。
    """
    text = text.strip()
    if not text:
        raise ValueError("文件内容为空")

    pieces = split_text(text, size=400, overlap=80)
    if not pieces:
        raise ValueError("切块后没有内容")

    # 先把所有块的向量算出来（网络 IO，放在事务外面，别占着连接）
    vectors = await embed_texts(pieces)
    if len(vectors) != len(pieces):
        raise RuntimeError(f"向量数量不匹配：{len(vectors)} vs {len(pieces)}")

    async with SessionLocal() as s:
        # 幂等：同名文件先清掉旧的
        old_docs = (await s.execute(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.filename == filename,
            )
        )).scalars().all()
        for d in old_docs:
            await s.execute(delete(Chunk).where(Chunk.document_id == d.id))
            await s.delete(d)
        doc = Document(tenant_id=tenant_id, filename=filename)
        s.add(doc)
        await s.flush()          # 拿到自增 id，但事务还没提交
        doc_id = doc.id
        for i, (piece, vec) in enumerate(zip(pieces, vectors)):
            s.add(Chunk(
                document_id=doc_id,
                chunk_index=i,
                content=piece,
                embedding=vec,
            ))
        await s.commit()         # 一次提交，要么全成功，要么全回滚

    return doc_id, len(pieces)