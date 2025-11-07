"""数据库会话管理模块"""
from contextlib import contextmanager
from typing import Iterator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
import logging

from .config import CATEGORY_COLOR_PALETTE, DATABASE_URL, DEFAULT_CATEGORIES

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
    from .crud import ensure_default_assets  # noqa: WPS433

    Base.metadata.create_all(bind=engine)
    with session_scope() as session:
        ensure_default_assets(session)
    _apply_user_id_migrations()


def _apply_user_id_migrations() -> None:
    """Ensure existing 数据库表包含 user_id 字段及相关索引."""

    with engine.begin() as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())

        if "categories" in table_names:
            _ensure_category_type_columns(connection)
            _ensure_category_user_columns(connection)
            _ensure_category_color_columns(connection)
        if "bills" in table_names:
            _ensure_bill_user_columns(connection)
            _ensure_bill_asset_columns(connection)
            _ensure_bill_amount_columns(connection)


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
    desired_columns = ["user_id", "name"]
    unique_name = "uq_category_user_name"
    if "type" in columns:
        desired_columns = ["user_id", "name", "type"]
        unique_name = "uq_category_user_name_type"

    for index in list(indexes):
        if not index.get("unique"):
            continue
        column_names = index.get("column_names") or []
        if column_names == desired_columns and index.get("name") == unique_name:
            continue
        connection.execute(
            text(f"ALTER TABLE categories DROP INDEX `{index['name']}`")
        )

    inspector = inspect(connection)
    indexes = inspector.get_indexes("categories")
    if not any(
        index.get("unique")
        and index.get("name") == unique_name
        and (index.get("column_names") or []) == desired_columns
        for index in indexes
    ):
        columns_expr = ", ".join(desired_columns)
        connection.execute(
            text(
                "ALTER TABLE categories ADD UNIQUE INDEX "
                f"{unique_name} ({columns_expr})"
            )
        )

    if not any(index.get("name") == "ix_categories_user_id" for index in indexes):
        connection.execute(
            text("CREATE INDEX ix_categories_user_id ON categories (user_id)")
        )


def _ensure_category_type_columns(connection) -> None:
    """为分类表添加类型字段并设置默认值."""

    inspector = inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("categories")}
    if "type" not in columns:
        connection.execute(text("ALTER TABLE categories ADD COLUMN type VARCHAR(16)"))
        inspector = inspect(connection)
        columns = {col["name"] for col in inspector.get_columns("categories")}

    connection.execute(
        text(
            "UPDATE categories SET type = 'expense' "
            "WHERE type IS NULL OR type = ''"
        )
    )
    connection.execute(
        text("ALTER TABLE categories MODIFY COLUMN type VARCHAR(16) NOT NULL")
    )


def _ensure_category_color_columns(connection) -> None:
    """为分类表添加颜色字段并填充默认颜色."""

    inspector = inspect(connection)
    dialect_name = connection.dialect.name
    columns = {col["name"] for col in inspector.get_columns("categories")}
    if "color" not in columns:
        connection.execute(text("ALTER TABLE categories ADD COLUMN color VARCHAR(7)"))
        inspector = inspect(connection)

    result = connection.execute(
        text("SELECT id, name, color FROM categories ORDER BY id")
    ).mappings().all()
    if not result:
        return

    default_color_map = {
        item["name"]: item.get("color")
        for item in DEFAULT_CATEGORIES
        if item.get("color")
    }

    used_colors = {
        row["color"]
        for row in result
        if row["color"] is not None and row["color"].strip() != ""
    }
    palette_cycle = [color for color in CATEGORY_COLOR_PALETTE if color not in used_colors]

    def _next_color() -> str:
        nonlocal palette_cycle
        if not palette_cycle:
            palette_cycle = list(CATEGORY_COLOR_PALETTE)
        color = palette_cycle.pop(0)
        while color in used_colors and palette_cycle:
            color = palette_cycle.pop(0)
        return color if color not in used_colors else CATEGORY_COLOR_PALETTE[0]

    for row in result:
        if row["color"] is not None and row["color"].strip() != "":
            continue

        desired_color = default_color_map.get(row["name"])
        if desired_color and desired_color not in used_colors:
            color_value = desired_color
        else:
            color_value = _next_color()
        connection.execute(
            text("UPDATE categories SET color = :color WHERE id = :id"),
            {"color": color_value, "id": row["id"]},
        )
        used_colors.add(color_value)

    connection.execute(
        text(
            "UPDATE categories SET color = :fallback WHERE color IS NULL OR color = ''"
        ),
        {"fallback": CATEGORY_COLOR_PALETTE[0]},
    )

    if dialect_name.startswith("mysql"):
        connection.execute(
            text("ALTER TABLE categories MODIFY COLUMN color VARCHAR(7) NOT NULL")
        )


def _ensure_bill_asset_columns(connection) -> None:
    """确保账单表包含资产字段并填充默认值."""

    inspector = inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("bills")}

    if "source_asset_id" not in columns:
        connection.execute(text("ALTER TABLE bills ADD COLUMN source_asset_id INTEGER"))
        inspector = inspect(connection)
        columns = {col["name"] for col in inspector.get_columns("bills")}

    if "target_asset_id" not in columns:
        connection.execute(text("ALTER TABLE bills ADD COLUMN target_asset_id INTEGER"))

    cny_asset_id = _get_asset_id(connection, "CNY")
    if cny_asset_id is not None:
        connection.execute(
            text(
                "UPDATE bills SET source_asset_id = :asset_id "
                "WHERE source_asset_id IS NULL"
            ),
            {"asset_id": cny_asset_id},
        )
        connection.execute(
            text(
                "UPDATE bills SET target_asset_id = :asset_id "
                "WHERE target_asset_id IS NULL"
            ),
            {"asset_id": cny_asset_id},
        )

    dialect_name = connection.dialect.name
    if dialect_name.startswith("mysql"):
        connection.execute(
            text("ALTER TABLE bills MODIFY COLUMN source_asset_id INTEGER NOT NULL")
        )
        connection.execute(
            text("ALTER TABLE bills MODIFY COLUMN target_asset_id INTEGER NOT NULL")
        )


def _ensure_bill_amount_columns(connection) -> None:
    """确保账单表包含资产数量字段并填充默认值."""

    inspector = inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("bills")}

    if "source_amount" in columns:
        connection.execute(text("ALTER TABLE bills DROP COLUMN source_amount"))
    if "target_amount" not in columns:
        connection.execute(text("ALTER TABLE bills ADD COLUMN target_amount FLOAT"))

    connection.execute(
        text(
            "UPDATE bills SET target_amount = amount "
            "WHERE target_amount IS NULL"
        )
    )

    dialect_name = connection.dialect.name
    if dialect_name.startswith("mysql"):
        connection.execute(
            text("ALTER TABLE bills MODIFY COLUMN target_amount FLOAT NOT NULL")
        )


def _get_asset_id(connection, name: str) -> int | None:
    """获取指定名称的资产 ID."""

    result = connection.execute(
        text("SELECT id FROM assets WHERE name = :name"),
        {"name": name},
    ).first()
    if result:
        return int(result[0])
    return None

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
