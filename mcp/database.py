"""数据库会话管理模块"""
from contextlib import contextmanager
from typing import Iterator
from sqlalchemy import create_engine, inspect, text
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
    _apply_user_id_migrations()


def _apply_user_id_migrations() -> None:
    """Ensure existing 数据库表包含 user_id 字段及相关索引."""

    with engine.begin() as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())

        if "categories" in table_names:
            _ensure_category_user_columns(connection)
        if "bills" in table_names:
            _ensure_bill_user_columns(connection)


def _ensure_category_user_columns(connection) -> None:
    """为分类表添加 user_id 相关结构."""

    inspector = inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("categories")}
    if "user_id" not in columns:
        connection.execute(
            text("ALTER TABLE categories ADD COLUMN user_id VARCHAR(64) DEFAULT 'legacy'")
        )
        connection.execute(
            text("UPDATE categories SET user_id = 'legacy' WHERE user_id IS NULL")
        )
        connection.execute(
            text("ALTER TABLE categories MODIFY COLUMN user_id VARCHAR(64) NOT NULL")
        )

    inspector = inspect(connection)
    indexes = inspector.get_indexes("categories")
    for index in indexes:
        if index.get("unique") and index.get("column_names") == ["name"]:
            connection.execute(
                text(
                    f"ALTER TABLE categories DROP INDEX `{index['name']}`"
                )
            )

    inspector = inspect(connection)
    indexes = inspector.get_indexes("categories")
    if not any(index.get("unique") and index.get("name") == "uq_category_user_name" for index in indexes):
        connection.execute(
            text(
                "ALTER TABLE categories ADD UNIQUE INDEX "
                "uq_category_user_name (user_id, name)"
            )
        )

    if not any(index.get("name") == "ix_categories_user_id" for index in indexes):
        connection.execute(
            text("CREATE INDEX ix_categories_user_id ON categories (user_id)")
        )


def _ensure_bill_user_columns(connection) -> None:
    """为账单表添加 user_id 相关结构."""

    inspector = inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("bills")}
    if "user_id" not in columns:
        connection.execute(
            text("ALTER TABLE bills ADD COLUMN user_id VARCHAR(64) DEFAULT 'legacy'")
        )
        connection.execute(
            text("UPDATE bills SET user_id = 'legacy' WHERE user_id IS NULL")
        )
        connection.execute(
            text("ALTER TABLE bills MODIFY COLUMN user_id VARCHAR(64) NOT NULL")
        )

    inspector = inspect(connection)
    indexes = inspector.get_indexes("bills")
    if not any(index.get("name") == "ix_bills_user_id" for index in indexes):
        connection.execute(text("CREATE INDEX ix_bills_user_id ON bills (user_id)"))
