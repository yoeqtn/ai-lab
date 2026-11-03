import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from llm import stream_chat

app = FastAPI(title="ai-lab")

@app.get("/")
def read_root():
    return {"msg": "hello, ai-lab"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/chat")
async def chat(q: str):
    # 直接把异步生成器交给 StreamingResponse，边生成边发给浏览器
    return StreamingResponse(
        stream_chat(q),
        media_type="text/plain; charset=utf-8",
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)