from sqlalchemy import create_engine, ForeignKey, String, select, event
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, selectinload,
)


class Base(DeclarativeBase):
    pass


class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    books: Mapped[list["Book"]] = relationship(back_populates="author")


class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))
    author: Mapped["Author"] = relationship(back_populates="books")


engine = create_engine("sqlite+pysqlite:///./n1_demo.db")
Session = sessionmaker(engine)

counter = {"n": 0}


@event.listens_for(engine, "before_cursor_execute")
def count_sql(conn, cursor, statement, parameters, context, executemany):
    counter["n"] += 1


with engine.begin() as conn:
    Base.metadata.drop_all(conn)
    Base.metadata.create_all(conn)

with Session() as s:
    for i in range(10):
        a = Author(name=f"作者{i}")
        a.books = [Book(title=f"书{i}-1"), Book(title=f"书{i}-2")]
        s.add(a)
    s.commit()

with Session() as s:
    counter["n"] = 0
    authors = s.scalars(select(Author)).all()
    total = sum(len(a.books) for a in authors)
    print(f"写法A(N+1)        : {len(authors)} 个作者 / {total} 本书 -> 共 {counter['n']} 条 SQL")

with Session() as s:
    counter["n"] = 0
    authors = s.scalars(select(Author).options(selectinload(Author.books))).all()
    total = sum(len(a.books) for a in authors)
    print(f"写法B(selectinload): {len(authors)} 个作者 / {total} 本书 -> 共 {counter['n']} 条 SQL")

print()
print("结论：作者越多，写法 A 的 SQL 条数线性增长(1+N)；写法 B 恒定为 2 条。")