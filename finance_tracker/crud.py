"""Data access helpers for categories and transactions."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Category, Transaction


def list_categories(session: Session) -> list[Category]:
    return list(session.scalars(select(Category).order_by(Category.name)))


def get_category_by_name(session: Session, name: str) -> Category | None:
    return session.scalars(select(Category).where(Category.name == name)).first()


def create_transaction(
    session: Session, *, amount: Decimal, category: Category, description: str
) -> Transaction:
    transaction = Transaction(amount=amount, category=category, description=description)
    session.add(transaction)
    session.flush()
    session.refresh(transaction)
    return transaction
