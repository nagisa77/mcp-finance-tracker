"""Pydantic 模型."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CategoryRead(BaseModel):
    """分类输出模型."""

    id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class BillCreate(BaseModel):
    """账单创建输入模型."""

    amount: float = Field(..., description="金额，正数为支出，负数为收入")
    category: Optional[str] = Field(default=None, description="分类名称")
    description: Optional[str] = Field(default=None, description="账单描述")

    @field_validator("amount")
    @classmethod
    def amount_cannot_be_zero(cls, value: float) -> float:
        if value == 0:
            raise ValueError("金额不能为 0")
        return value

    @property
    def bill_type(self) -> str:
        return "expense" if self.amount >= 0 else "income"

    @property
    def abs_amount(self) -> float:
        return abs(self.amount)
