import os
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

EMBED_MODEL = os.getenv("EMBED_MODEL", "qwen3.7-text-embedding")
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "qwen-max")
BASE_URL = os.getenv("DASHSCOPE_BASE_URL",
                     "https://dashscope.aliyuncs.com/compatible-mode/v1")
DATABASE_URL = os.getenv("DATABASE_URL")


