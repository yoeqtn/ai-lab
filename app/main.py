"""FastAPI 入口：负责生命周期与路由装配。

读这个文件的顺序（很重要）：
  1. lifespan  —— 创建 checkpointer、编译图、挂到 app.state.graph
  2. app = FastAPI(lifespan=lifespan)   ← 必须在 include_router 之前
  3. include_router —— 具体接口在 app/api/ 下

启动：uvicorn app.main:app --reload
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import text

from app.agent.checkpointer import PG_URI
from app.agent.graph import build_graph
from app.api import admin, chat, knowledge
from app.core.db import engine

# Windows 默认的 ProactorEventLoop 不被 psycopg 异步连接支持，
# AsyncPostgresSaver 会在启动时报 InterfaceError。必须在创建事件循环前切换。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============ 1. 生命周期 ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    # checkpointer 是异步上下文管理器，只能在事件循环里开、在这里关
    async with AsyncPostgresSaver.from_conn_string(PG_URI) as cp:
        await cp.setup()                    # 建 4 张表，幂等，每次启动都安全
        app.state.graph = build_graph(cp)   # ← app.state.graph 就是这一行挂上去的
        logger.info("checkpointer 就绪，Agent 图已编译")
        yield                               # 服务运行期间，cp 一直开着
    # 先退出上面的 with（关掉 checkpointer 连接），再释放数据库连接池
    await engine.dispose()


# ============ 2. 创建 app（必须在路由之前）============
app = FastAPI(title="AI Lab", version="0.2.0", lifespan=lifespan)

app.include_router(chat.router)
app.include_router(knowledge.router)
app.include_router(admin.router)


# ============ 3. 健康检查 ============
@app.get("/health", tags=["ops"])
async def health():
    """给负载均衡/容器编排用的探针：数据库不通就返回 503。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("health check failed")
        return JSONResponse({"status": "degraded", "database": "down"}, status_code=503)
    return {"status": "ok", "database": "up", "graph": "ready"}
