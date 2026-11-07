from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def connect(url):
    args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=args, pool_pre_ping=True)
    return engine, sessionmaker(engine, expire_on_commit=False)
