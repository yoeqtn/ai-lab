from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import async_database_url

# 数据库地址统一来自 .env；换库只改配置，其余代码不动。
engine = create_async_engine(
    async_database_url(), echo=True
)

SessionLocal = async_sessionmaker(
    engine, expire_on_commit=False
)
