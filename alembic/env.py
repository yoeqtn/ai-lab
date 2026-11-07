import asyncio
import logging
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import async_database_url

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 数据库地址以 .env 为准，alembic.ini 里的值只作后备
config.set_main_option("sqlalchemy.url", async_database_url())

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from app.models import Base  # noqa: E402  (必须在 alembic config 初始化之后导入)

target_metadata = Base.metadata

# other values from the config, defined by the needs of .env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # 先确保 pgvector 扩展存在，否则 chunks.embedding 列无法创建。
        # 没有超级用户权限时降级为警告，由 DBA 手动创建。
        try:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.commit()
        except Exception:
            logging.getLogger("alembic").warning(
                "无法自动创建 pgvector 扩展，请手动执行 "
                "CREATE EXTENSION vector;",
                exc_info=True,
            )
            await connection.rollback()
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
