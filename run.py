"""跨平台启动入口。

Windows 上 psycopg 的异步连接（LangGraph AsyncPostgresSaver 使用）不支持默认的
ProactorEventLoop，而 uvicorn 在导入 app 之前就创建了事件循环，所以在 app 里
设置策略来不及。这里在启动 uvicorn 之前指定 SelectorEventLoop。

用法：
    uv run python run.py                # 开发
    uv run python run.py --reload       # 热重载
"""
import asyncio
import sys

import uvicorn


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        loop = "run:selector_loop_factory"
    else:
        loop = "auto"

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        loop=loop,
        reload="--reload" in sys.argv,
    )
