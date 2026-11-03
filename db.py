from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# 今天用 SQLite：零安装。明天换 PostgreSQL 时，只改这一行，其余代码不动。
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_lab"

engine = create_async_engine(
    DATABASE_URL, echo=True
)

SessionLocal = async_sessionmaker(
    engine, expire_on_commit=False
)