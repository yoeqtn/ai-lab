import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_lab"

async def main():
    engine = create_async_engine(URL, echo=False)
    async with engine.connect() as conn:
        v = (await conn.execute(text("select version()"))).scalar()
        print("PG:", v.split(",")[0])

        # 没装 vector 扩展就装上（装过就什么都不做）
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.commit()

        rows = (await conn.execute(text("select extname, extversion from pg_extension"))).all()
        print("扩展:", rows)
        tables = (await conn.execute(text(
            "select tablename from pg_tables where schemaname = 'public' order by tablename"
        ))).scalars().all()
        print("表:", tables)
        cols = (await conn.execute(text(
            "select column_name, data_type, udt_name from information_schema.columns "
            "where table_name = 'chunks' order by ordinal_position"
        ))).all()
        for c in cols:
            print("列:", c)
    await engine.dispose()


asyncio.run(main())