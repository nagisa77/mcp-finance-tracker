"""数据库 CRUD 操作."""
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.orm import Session

from .config import DEFAULT_CATEGORIES
from .models import Bill, BillType, Category
from .schemas import BillCreate


def ensure_default_categories(session: Session) -> None:
    """确保默认分类存在."""
    existing_names = {
        name for name in session.scalars(select(Category.name)).all()
    }
    for category in DEFAULT_CATEGORIES:
        if category["name"] not in existing_names:
            session.add(Category(**category))


def list_categories(session: Session) -> List[Category]:
    """获取所有分类."""
    stmt = select(Category).order_by(Category.id)
    return session.scalars(stmt).all()


def get_categories_by_ids(session: Session, category_ids: Iterable[int]) -> List[Category]:
    """根据 ID 列表获取分类."""

    category_id_list = list(category_ids)
    if not category_id_list:
        return []

    stmt: Select = (
        select(Category)
        .where(Category.id.in_(category_id_list))
        .order_by(asc(Category.id))
    )
    return list(session.scalars(stmt).all())


def get_category_by_name(session: Session, name: str) -> Optional[Category]:
    """根据名称获取分类."""
    stmt = select(Category).where(Category.name == name)
    return session.scalars(stmt).first()


def get_category_by_id(session: Session, category_id: int) -> Optional[Category]:
    """根据 ID 获取分类."""
    stmt = select(Category).where(Category.id == category_id)
    return session.scalars(stmt).first()


def create_bill(session: Session, data: BillCreate, category: Optional[Category]) -> Bill:
    """创建账单记录."""
    bill = Bill(
        amount=data.amount,
        type=BillType(data.type),
        description=data.description,
        category=category,
    )
    session.add(bill)
    session.flush()
    session.refresh(bill)
    return bill


def get_expense_summary_by_category(
    session: Session,
    start: datetime,
    end: datetime,
) -> list[dict[str, object]]:
    """在指定时间区间内按分类统计支出."""

    stmt: Select = (
        select(
            Bill.category_id.label("category_id"),
            func.coalesce(Category.name, "未分类").label("category_name"),
            func.sum(Bill.amount).label("total_amount"),
        )
        .join(Category, Bill.category_id == Category.id, isouter=True)
        .where(
            Bill.type == BillType.EXPENSE,
            Bill.created_at >= start,
            Bill.created_at < end,
        )
        .group_by(Bill.category_id, Category.name)
        .order_by(desc("total_amount"))
    )

    result = list(session.execute(stmt))
    breakdown = [
        {
            "category_id": row.category_id,
            "category_name": row.category_name,
            "total_amount": float(row.total_amount or 0),
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
) -> float:
    """统计指定时间区间内的总支出."""

    total_stmt: Select = (
        select(func.coalesce(func.sum(Bill.amount), 0))
        .where(
            Bill.type == BillType.EXPENSE,
            Bill.created_at >= start,
            Bill.created_at < end,
        )
    )
    return float(session.execute(total_stmt).scalar_one())


def get_category_filtered_expenses(
    session: Session,
    start: datetime,
    end: datetime,
    category_ids: Iterable[int],
    limit: int = 20,
) -> list[Bill]:
    """获取指定分类下的消费账单，按金额倒序排列."""

    category_id_list = list(category_ids)
    if not category_id_list:
        return []

    stmt: Select = (
        select(Bill)
        .where(
            Bill.type == BillType.EXPENSE,
            Bill.created_at >= start,
            Bill.created_at < end,
            Bill.category_id.in_(category_id_list),
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
) -> float:
    """统计指定分类下的总支出."""

    category_id_list = list(category_ids)
    if not category_id_list:
        return 0.0

    total_stmt: Select = (
        select(func.coalesce(func.sum(Bill.amount), 0))
        .where(
            Bill.type == BillType.EXPENSE,
            Bill.created_at >= start,
            Bill.created_at < end,
            Bill.category_id.in_(category_id_list),
        )
    )
    return float(session.execute(total_stmt).scalar_one())
