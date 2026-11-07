"""集中读取 .env 配置。其他模块只从这里拿值，不要各自读环境变量。"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 无论从哪个工作目录启动，都读项目根目录的 .env
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# ---- LLM / Embedding（阿里云百炼）----
EMBED_MODEL = os.getenv("EMBED_MODEL", "qwen3.7-text-embedding")
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "qwen-max")
BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
EMBED_DIM = int(os.getenv("EMBED_DIM", "1024"))
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "10"))
EMBED_CONCURRENCY = int(os.getenv("EMBED_CONCURRENCY", "3"))

# ---- 数据库 ----
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ai_lab",
)
SQL_ECHO = _as_bool(os.getenv("SQL_ECHO"), default=False)

# ---- 业务参数 ----
# 检索结果的余弦距离上限（1 - 余弦相似度），越小越严格
REJECT_DISTANCE = float(os.getenv("REJECT_DISTANCE", "0.55"))
# 单条聊天消息的最大字符数
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "4000"))
# 单个上传文件解析后的最大字符数
MAX_UPLOAD_CHARS = int(os.getenv("MAX_UPLOAD_CHARS", "200000"))

# ---- 接口鉴权（留空 = 本地开发不校验）----
API_TOKEN = os.getenv("APP_API_TOKEN", "")

if not API_KEY:
    logger.warning("DASHSCOPE_API_KEY 未配置，LLM/Embedding 调用会失败，请检查 .env")


def async_database_url() -> str:
    """SQLAlchemy 异步引擎用的 DSN（asyncpg 驱动）。"""
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


def sync_database_url() -> str:
    """LangGraph checkpointer 用的 psycopg DSN（不接受 +asyncpg 后缀）。"""
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
