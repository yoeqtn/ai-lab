from pathlib import Path
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from llm import stream_chat, stream_rag
from search import search_chunks
from ingest import ingest_text
from parsers import ALLOWED_SUFFIX, extract_text
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from graph import graph
app = FastAPI(title="ai-lab")

MAX_BYTES = 2 * 1024 * 1024          # 2MB
# ALLOWED_SUFFIX 已从 parsers 导入，这里不要再定义

class AgentIn(BaseModel):
    message: str

@app.get("/")
def read_root():
    return {"msg": "hello, ai-lab"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/chat")
async def chat(q: str):
    return StreamingResponse(
        stream_chat(q),
        media_type="text/plain; charset=utf-8",
    )

@app.get("/ask")
async def ask(q: str):
    rows = await search_chunks(q, top_k=3)
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

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    # 1. 文件名清洗：只取最后一段，防 ../../etc/passwd 这类路径穿越
    safe_name = Path(file.filename or "untitled.txt").name

    # 2. 类型白名单
    if Path(safe_name).suffix.lower() not in ALLOWED_SUFFIX:
        raise HTTPException(400, "只支持 txt / md / pdf / docx")

    # 3. 大小限制
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(400, "文件不能超过 2MB")
    if not raw:
        raise HTTPException(400, "文件是空的")

    # 4. 解析成纯文本（PDF / Word / 纯文本统一入口）
    try:
        text = extract_text(safe_name, raw)
    except ValueError as e:
        raise HTTPException(400, str(e))


    # 5. 入库
    try:
        doc_id, n = await ingest_text(safe_name, text)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "document_id": doc_id,
        "filename": safe_name,
        "chunks": n,
        "chars": len(text),
    }
@app.post("/agent")
async def agent_chat(body: AgentIn):
    """能自己决定调什么工具的对话接口，流式返回。"""

    async def gen():
        async for chunk, meta in graph.astream(
            {"messages": [HumanMessage(content=body.message)]},
            stream_mode="messages",
        ):
            # 只要模型输出的 token，丢掉工具节点的执行结果
            if meta.get("langgraph_node") != "agent":
                continue

            # langchain-core 1.x 用 .text 属性；老版本可能是 .content
            text = getattr(chunk, "text", None) or ""
            if not isinstance(text, str):
                text = ""
            if text:
                yield text

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)