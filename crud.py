"""数据库 CRUD 操作."""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import DEFAULT_CATEGORIES
from models import Bill, Category
from schemas import BillCreate


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


def get_category_by_name(session: Session, name: str) -> Optional[Category]:
    """根据名称获取分类."""
    stmt = select(Category).where(Category.name == name)
    return session.scalars(stmt).first()


def create_bill(session: Session, data: BillCreate, category: Optional[Category]) -> Bill:
    """创建账单记录."""
    bill = Bill(
        amount=data.abs_amount,
        type=data.bill_type,
        description=data.description,
        category=category,
    )
    session.add(bill)
    session.flush()
    session.refresh(bill)
    return bill
