"""把 LangGraph 的状态存进 PostgreSQL，支持跨重启恢复。"""
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import settings

# 关键：checkpointer 要 psycopg 格式，你 .env 里是 asyncpg 格式，必须换掉前缀。
#   postgresql+asyncpg://postgres:postgres@localhost:5432/ai_lab   ← SQLAlchemy 用
#   postgresql://postgres:postgres@localhost:5432/ai_lab           ← checkpointer 用

PG_URI = settings.DATABASE_URL
