"""数据库 CRUD 操作."""
from datetime import datetime, timedelta
from typing import Iterable, List, Literal, Optional

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.orm import Session

from .config import DEFAULT_ASSETS, DEFAULT_CATEGORIES, UNCATEGORIZED_CATEGORY_COLOR
from .models import Asset, Bill, BillType, Category, CategoryType
from .schemas import BillCreate


def ensure_default_assets(session: Session) -> None:
    """确保默认资产存在."""

    existing_assets = {
        asset.name: asset
        for asset in session.scalars(select(Asset).order_by(asc(Asset.id))).all()
    }
    for asset in DEFAULT_ASSETS:
        name = asset["name"].strip()
        if not name:
            continue
        existing = existing_assets.get(name)
        if existing is None:
            session.add(
                Asset(
                    name=name,
                    description=asset.get("description"),
                )
            )
            continue

        description = asset.get("description")
        if description is not None and existing.description != description:
            existing.description = description
            session.add(existing)


def get_asset_by_name(session: Session, name: str) -> Asset | None:
    """根据名称获取资产."""

    stmt = select(Asset).where(Asset.name == name)
    return session.scalars(stmt).first()


def get_asset_by_id(session: Session, asset_id: int) -> Asset | None:
    """根据 ID 获取资产."""

    stmt = select(Asset).where(Asset.id == asset_id)
    return session.scalars(stmt).first()


def ensure_default_categories(session: Session, user_id: str) -> None:
    """确保默认分类存在."""

    existing_categories = {
        (category.name, category.type): category
        for category in session.scalars(
            select(Category).where(Category.user_id == user_id)
        ).all()
    }
    for category in DEFAULT_CATEGORIES:
        category_type = CategoryType(category.get("type", CategoryType.EXPENSE))
        key = (category["name"], category_type)
        existing = existing_categories.get(key)
        if existing is None:
            session.add(
                Category(
                    user_id=user_id,
                    name=category["name"],
                    description=category.get("description"),
                    color=category.get("color", "#5E81AC"),
                    type=category_type,
                )
            )
            continue

        updated = False
        if existing.description != category.get("description"):
            existing.description = category.get("description")
            updated = True
        if category.get("color") and existing.color != category["color"]:
            existing.color = category["color"]
            updated = True
        if existing.type != category_type:
            existing.type = category_type
            updated = True
        if updated:
            session.add(existing)


def list_categories(session: Session, user_id: str) -> List[Category]:
    """获取所有分类."""
    stmt = (
        select(Category)
        .where(Category.user_id == user_id)
        .order_by(Category.id)
    )
    return session.scalars(stmt).all()


def get_categories_by_ids(
    session: Session, category_ids: Iterable[int], user_id: str
) -> List[Category]:
    """根据 ID 列表获取分类."""

    category_id_list = list(category_ids)
    if not category_id_list:
        return []

    stmt: Select = (
        select(Category)
        .where(
            Category.user_id == user_id,
            Category.id.in_(category_id_list),
        )
        .order_by(asc(Category.id))
    )
    return list(session.scalars(stmt).all())


def get_category_by_name(
    session: Session,
    name: str,
    user_id: str,
    category_type: CategoryType | None = None,
) -> Optional[Category]:
    """根据名称获取分类."""
    stmt = select(Category).where(
        Category.user_id == user_id,
        Category.name == name,
    )
    if category_type is not None:
        stmt = stmt.where(Category.type == category_type)
    return session.scalars(stmt).first()


def get_category_by_id(
    session: Session, category_id: int, user_id: str
) -> Optional[Category]:
    """根据 ID 获取分类."""
    stmt = select(Category).where(
        Category.user_id == user_id,
        Category.id == category_id,
    )
    return session.scalars(stmt).first()


def create_bill(
    session: Session,
    data: BillCreate,
    category: Optional[Category],
    user_id: str,
) -> Bill:
    """创建账单记录."""
    bill_type = BillType(data.type)
    if category is not None and category.type != CategoryType(bill_type.value):
        raise ValueError("所选分类类型与账单类型不匹配")

    if data.source_asset_id is None or data.target_asset_id is None:
        raise ValueError("记录账单时必须指定源资产与目标资产")

    source_amount = data.source_amount if data.source_amount is not None else data.amount
    target_amount = data.target_amount if data.target_amount is not None else data.amount

    bill = Bill(
        user_id=user_id,
        amount=data.amount,
        type=bill_type,
        description=data.description,
        category=category,
        source_asset_id=data.source_asset_id,
        target_asset_id=data.target_asset_id,
        source_amount=source_amount,
        target_amount=target_amount,
    )
    session.add(bill)
    session.flush()
    session.refresh(bill)
    return bill


def get_expense_summary_by_category(
    session: Session,
    start: datetime,
    end: datetime,
    user_id: str,
    category_ids: Iterable[int] | None = None,
    bill_type: BillType = BillType.EXPENSE,
) -> list[dict[str, object]]:
    """在指定时间区间内按分类统计账单金额."""

    stmt: Select = (
        select(
            Bill.category_id.label("category_id"),
            func.coalesce(Category.name, "未分类").label("category_name"),
            func.sum(Bill.amount).label("total_amount"),
            func.coalesce(Category.color, "").label("color"),
        )
        .join(Category, Bill.category_id == Category.id, isouter=True)
        .where(
            Bill.type == bill_type,
            Bill.created_at >= start,
            Bill.created_at < end,
            Bill.user_id == user_id,
        )
        .group_by(Bill.category_id, Category.name, Category.color)
        .order_by(desc("total_amount"))
    )

    category_id_list = list(category_ids) if category_ids is not None else []
    if category_ids is not None:
        if not category_id_list:
            return []
        stmt = stmt.where(Bill.category_id.in_(category_id_list))

    result = list(session.execute(stmt))
    breakdown = [
        {
            "category_id": row.category_id,
            "category_name": row.category_name,
            "total_amount": float(row.total_amount or 0),
            "color": row.color or UNCATEGORIZED_CATEGORY_COLOR,
        }
        for row in result
    ]

    total_amount = sum(item["total_amount"] for item in breakdown)
    if total_amount <= 0:
        for item in breakdown:
            item["percentage"] = 0.0
    else:
        for item in breakdown:
            item["percentage"] = item["total_amount"] / total_amount * 100

    return breakdown


def get_total_expense(
    session: Session,
    start: datetime,
    end: datetime,
    user_id: str,
    category_ids: Iterable[int] | None = None,
    bill_type: BillType = BillType.EXPENSE,
) -> float:
    """统计指定时间区间内的账单总金额."""

    total_stmt: Select = (
        select(func.coalesce(func.sum(Bill.amount), 0))
        .where(
            Bill.type == bill_type,
            Bill.created_at >= start,
            Bill.created_at < end,
            Bill.user_id == user_id,
        )
    )
    if category_ids is not None:
        category_id_list = list(category_ids)
        if not category_id_list:
            return 0.0
        total_stmt = total_stmt.where(Bill.category_id.in_(category_id_list))
    return float(session.execute(total_stmt).scalar_one())


def get_category_filtered_expenses(
    session: Session,
    start: datetime,
    end: datetime,
    category_ids: Iterable[int],
    user_id: str,
    limit: int = 20,
    bill_type: BillType = BillType.EXPENSE,
) -> list[Bill]:
    """获取指定分类下的账单，按金额倒序排列."""

    category_id_list = list(category_ids)
    if not category_id_list:
        return []

    stmt: Select = (
        select(Bill)
        .where(
            Bill.type == bill_type,
            Bill.created_at >= start,
            Bill.created_at < end,
            Bill.category_id.in_(category_id_list),
            Bill.user_id == user_id,
        )
        .order_by(desc(Bill.amount), asc(Bill.id))
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def get_total_expense_for_categories(
    session: Session,
    start: datetime,
    end: datetime,
    category_ids: Iterable[int],
    user_id: str,
    bill_type: BillType = BillType.EXPENSE,
) -> float:
    """统计指定分类下的账单总金额."""

    category_id_list = list(category_ids)
    if not category_id_list:
        return 0.0

    total_stmt: Select = (
        select(func.coalesce(func.sum(Bill.amount), 0))
        .where(
            Bill.type == bill_type,
            Bill.created_at >= start,
            Bill.created_at < end,
            Bill.category_id.in_(category_id_list),
            Bill.user_id == user_id,
        )
    )
    return float(session.execute(total_stmt).scalar_one())


def get_expense_timeline(
    session: Session,
    start: datetime,
    end: datetime,
    user_id: str,
    granularity: Literal["month", "week", "day"],
    category_ids: Iterable[int] | None = None,
    bill_type: BillType = BillType.EXPENSE,
) -> list[dict[str, object]]:
    """Aggregate bill amounts into ordered time buckets for the given granularity."""

    category_id_list = list(category_ids or [])

    stmt: Select = (
        select(Bill.created_at, Bill.amount)
        .where(
            Bill.type == bill_type,
            Bill.created_at >= start,
            Bill.created_at < end,
            Bill.user_id == user_id,
        )
        .order_by(asc(Bill.created_at))
    )

    if category_id_list:
        stmt = stmt.where(Bill.category_id.in_(category_id_list))

    results = session.execute(stmt).all()

    def _strip_timezone(value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.replace(tzinfo=None)
        return value

    def _floor_to_granularity(value: datetime) -> datetime:
        if granularity == "day":
            return value.replace(hour=0, minute=0, second=0, microsecond=0)
        if granularity == "week":
            floored = value - timedelta(days=value.weekday())
            return floored.replace(hour=0, minute=0, second=0, microsecond=0)
        if granularity == "month":
            return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        raise ValueError("不支持的统计颗粒度。")

    def _advance(value: datetime) -> datetime:
        if granularity == "day":
            return value + timedelta(days=1)
        if granularity == "week":
            return value + timedelta(weeks=1)
        if granularity == "month":
            year = value.year + (value.month // 12)
            month = value.month % 12 + 1
            return value.replace(year=year, month=month, day=1)
        raise ValueError("不支持的统计颗粒度。")

    def _format_label(value: datetime) -> str:
        if granularity == "day":
            return value.strftime("%Y-%m-%d")
        if granularity == "week":
            iso = value.isocalendar()
            return f"{iso.year:04d}-W{iso.week:02d}"
        if granularity == "month":
            return value.strftime("%Y-%m")
        raise ValueError("不支持的统计颗粒度。")

    def _format_display_label(value: datetime) -> str:
        if granularity == "day":
            return value.strftime("%m-%d")
        if granularity == "week":
            iso = value.isocalendar()
            return f"W{iso.week:02d}"
        if granularity == "month":
            return value.strftime("%m月")
        raise ValueError("不支持的统计颗粒度。")

    buckets: list[dict[str, object]] = []
    if start >= end:
        return buckets

    current = _floor_to_granularity(start)
    while current < start:
        current = _advance(current)

    while current < end:
        next_boundary = _advance(current)
        buckets.append(
            {
                "label": _format_label(current),
                "display_label": _format_display_label(current),
                "start": current,
                "end": next_boundary if next_boundary <= end else end,
                "total_expense": 0.0,
            }
        )
        current = next_boundary

    bucket_map = {bucket["start"]: bucket for bucket in buckets}

    for row in results:
        created_at = _strip_timezone(row.created_at)
        bucket_start = _floor_to_granularity(created_at)
        bucket = bucket_map.get(bucket_start)
        if bucket is None:
            continue
        bucket["total_expense"] = float(bucket.get("total_expense", 0.0)) + float(
            row.amount or 0.0
        )

    return buckets
