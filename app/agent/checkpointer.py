"""把 LangGraph 的状态存进 PostgreSQL，支持跨重启恢复。"""
from app.core.config import sync_database_url

# 关键：checkpointer 要 psycopg 格式，.env 里是标准 postgresql:// 格式。
#   postgresql+asyncpg://postgres:postgres@localhost:5432/ai_lab   ← SQLAlchemy 用
#   postgresql://postgres:postgres@localhost:5432/ai_lab           ← checkpointer 用
PG_URI = sync_database_url()
