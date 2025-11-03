"""Default seeding helpers for the finance tracker database."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Category

DEFAULT_CATEGORIES = [
    ("餐饮", "日常餐饮、饮料等支出"),
    ("交通", "公交、地铁、打车等出行费用"),
    ("购物", "服饰、数码等消费"),
    ("住房", "房租、按揭、水电等"),
    ("工资", "工资或其他固定收入"),
    ("其他", "不属于以上类别的支出或收入"),
]


def seed_default_categories(session: Session) -> None:
    """Insert default categories when the table is empty."""
    existing = session.execute(select(Category.id)).first()
    if existing is not None:
        return

    for name, description in DEFAULT_CATEGORIES:
        session.add(Category(name=name, description=description))
