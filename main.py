import uvicorn
from fastapi import FastAPI

app = FastAPI(title="ai-lab")


@app.get("/")
def read_root():
    return {"msg": "hello, ai-lab"}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    # 有这几行，你就能直接点 PyCharm 的绿三角启动，不用记 uvicorn 命令
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)