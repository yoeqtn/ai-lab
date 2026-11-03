import asyncio
from sqlalchemy import select
from db import engine, SessionLocal
from models import Base, User, Document


async def main():
    # 每次从干净的库开始，方便反复运行而不报"重复邮箱"
    async with SessionLocal() as session:
        session.add(User(email="me@example.com", name="我"))
        session.add(Document(tenant_id="demo", filename="手册.pdf"))
        await session.commit()

        users = (await session.execute(select(User))).scalars().all()
        for u in users:
            print("USER ->", u.id, u.email, u.name)

        docs = (await session.execute(select(Document))).scalars().all()
        for d in docs:
            print("DOC  ->", d.id, d.tenant_id, d.filename)

    await engine.dispose()


asyncio.run(main())