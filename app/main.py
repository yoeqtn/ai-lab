"""FastAPI 入口：负责生命周期与路由装配。

读这个文件的顺序（很重要）：
  1. lifespan  —— 创建 checkpointer、编译图、挂到 app.state.graph
  2. app = FastAPI(lifespan=lifespan)   ← 必须在 include_router 之前
  3. include_router —— 具体接口在 app/api/ 下

启动：uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agent.checkpointer import PG_URI
from app.agent.graph import build_graph
from app.api import admin, chat, knowledge
from app.core.db import engine


# ============ 1. 生命周期 ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    # checkpointer 是异步上下文管理器，只能在事件循环里开、在这里关
    async with AsyncPostgresSaver.from_conn_string(PG_URI) as cp:
        await cp.setup()                    # 建 4 张表，幂等，每次启动都安全
        app.state.graph = build_graph(cp)   # ← app.state.graph 就是这一行挂上去的
        yield                               # 服务运行期间，cp 一直开着
    # 先退出上面的 with（关掉 checkpointer 连接），再释放数据库连接池
    await engine.dispose()


# ============ 2. 创建 app（必须在路由之前）============
app = FastAPI(title="AI Lab", lifespan=lifespan)

app.include_router(chat.router)
app.include_router(knowledge.router)
app.include_router(admin.router)
