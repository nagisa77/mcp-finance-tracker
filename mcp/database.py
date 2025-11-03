"""数据库会话管理模块"""
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import logging

from .config import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    expire_on_commit=False,
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """提供数据库会话的上下文管理器."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.exception("数据库会话执行失败: %s", exc)
        raise
    finally:
        session.close()


def init_database() -> None:
    """初始化数据库结构."""
    from .models import Base  # noqa: WPS433 - 延迟导入以避免循环依赖

    Base.metadata.create_all(bind=engine)
