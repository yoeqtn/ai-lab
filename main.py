from re import search

import uvicorn
from search import search_chunks
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from llm import stream_chat, stream_rag

app = FastAPI(title="ai-lab")


@app.get("/")
def read_root():
    return {"msg": "hello, ai-lab"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/chat")
async def chat(q: str):
    """纯聊天：不带资料，D5 的接口，留着做对比"""
    return StreamingResponse(
        stream_chat(q),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/ask")
async def ask(q: str):
    """RAG：先检索，再带资料回答"""
    rows = await search_chunks(q, top_k=3)

    # 只保留距离够近的，全都很远就当没查到
    rows = [(c, d) for c, d in rows if d < 0.55]

    if not rows:
        async def no_hit():
            yield "资料中没有提到相关内容，建议联系人工客服。"
        return StreamingResponse(no_hit(), media_type="text/plain; charset=utf-8")

    context = "\n\n".join(f"[{i + 1}] {c}" for i, (c, _) in enumerate(rows))
    return StreamingResponse(
        stream_rag(q, context),
        media_type="text/plain; charset=utf-8",
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)