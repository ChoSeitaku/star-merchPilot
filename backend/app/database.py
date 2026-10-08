"""数据库连接与会话管理。

约定：所有 datetime 一律使用 **UTC-naive**（见 ``utcnow``）。
SQLite 不保存时区，混用 aware/naive 会让 ``next_run_at <= now`` 之类的比较静默失效。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """返回 UTC-naive 当前时间（全项目统一时间来源）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


# SQLite 文件所在目录必须先存在，否则首次连接会直接失败
settings.ensure_dirs()

engine = create_engine(
    settings.database_url,
    # SQLite + FastAPI 线程池：连接会跨线程使用，必须关闭同线程校验
    connect_args={"check_same_thread": False} if _is_sqlite(settings.database_url) else {},
    future=True,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    """SQLite 默认不开启外键约束，且需要 WAL 提升并发读写表现。"""
    module = type(dbapi_connection).__module__
    if "sqlite" not in module:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：每请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def session_scope() -> Session:
    """后台任务使用的短生命周期会话（调用方负责关闭）。"""
    return SessionLocal()


def init_db() -> None:
    """建表（幂等）。"""
    from . import models  # noqa: F401  导入以注册全部表

    Base.metadata.create_all(bind=engine)
