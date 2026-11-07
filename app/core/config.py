"""集中读取 .env 配置。其他模块只从这里拿值，不要各自读环境变量。"""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 无论从哪个工作目录启动，都读项目根目录的 .env
load_dotenv(PROJECT_ROOT / ".env")

EMBED_MODEL = os.getenv("EMBED_MODEL", "qwen3.7-text-embedding")
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "qwen-max")
BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ai_lab",
)
EMBED_DIM = int(os.getenv("EMBED_DIM", "1024"))
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "10"))


def async_database_url() -> str:
    """SQLAlchemy 异步引擎用的 DSN（asyncpg 驱动）。"""
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


def sync_database_url() -> str:
    """LangGraph checkpointer 用的 psycopg DSN（不接受 +asyncpg 后缀）。"""
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
