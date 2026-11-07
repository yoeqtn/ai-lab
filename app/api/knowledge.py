"""知识库接口：/ 和 /upload。"""
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.ingest import ingest_text
from app.services.parsers import ALLOWED_SUFFIX, extract_text

router = APIRouter(tags=["knowledge"])

MAX_BYTES = 2 * 1024 * 1024          # 2MB


@router.get("/")
def read_root():
    return {"msg": "hello, ai-lab"}


@router.post("/upload")
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
