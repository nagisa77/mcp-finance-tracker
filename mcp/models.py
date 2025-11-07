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
    INVESTMENT = "investment"


class Asset(Base):
    """资产类型定义."""

    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("name", name="uq_asset_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    source_bills: Mapped[List["Bill"]] = relationship(
        back_populates="source_asset",
        cascade="all,delete",
        foreign_keys="Bill.source_asset_id",
    )
    target_bills: Mapped[List["Bill"]] = relationship(
        back_populates="target_asset",
        cascade="all,delete",
        foreign_keys="Bill.target_asset_id",
    )


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
        SAEnum(
            CategoryType,
            name="category_type",
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=CategoryType.EXPENSE,
    )

    bills: Mapped[List["Bill"]] = relationship(back_populates="category", cascade="all,delete")


class BillType(str, Enum):
    """账单类型枚举."""

    INCOME = "income"
    EXPENSE = "expense"
    INVESTMENT = "investment"


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
        SAEnum(
            BillType,
            name="bill_type",
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
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
    source_asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    target_asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    source_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    target_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_asset: Mapped[Asset] = relationship(
        back_populates="source_bills",
        foreign_keys=[source_asset_id],
    )
    target_asset: Mapped[Asset] = relationship(
        back_populates="target_bills",
        foreign_keys=[target_asset_id],
    )
