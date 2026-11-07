from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import config
from app.core.config import async_database_url

# 数据库地址统一来自 .env；换库只改配置，其余代码不动。
engine = create_async_engine(
    async_database_url(),
    echo=config.SQL_ECHO,          # 默认关闭；排查 SQL 时设置 SQL_ECHO=true
    pool_pre_ping=True,            # 连接被数据库回收后自动重连
)

SessionLocal = async_sessionmaker(
    engine, expire_on_commit=False
)
