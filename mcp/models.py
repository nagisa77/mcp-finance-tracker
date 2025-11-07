"""SQLAlchemy 模型定义."""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base."""


class CategoryType(str, Enum):
    """分类类型枚举."""

    INCOME = "income"
    EXPENSE = "expense"


class Category(Base):
    """账单分类."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "name", "type", name="uq_category_user_name_type"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#5E81AC")
    type: Mapped[CategoryType] = mapped_column(
        SAEnum(CategoryType, name="category_type", native_enum=False),
        nullable=False,
        default=CategoryType.EXPENSE,
    )

    bills: Mapped[List["Bill"]] = relationship(back_populates="category", cascade="all,delete")


class BillType(str, Enum):
    """账单类型枚举."""

    INCOME = "income"
    EXPENSE = "expense"


class Bill(Base):
    """账单记录."""

    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_bill_amount_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[BillType] = mapped_column(
        SAEnum(BillType, name="bill_type", native_enum=False), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    category: Mapped[Optional[Category]] = relationship(back_populates="bills")
