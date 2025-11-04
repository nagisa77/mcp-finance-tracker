"""Pydantic 模型."""
from datetime import datetime
from typing import List, Optional

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
    category: str = Field(..., description="分类名称")
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


class CategoryListResult(BaseModel):
    """Structured response for listing available categories."""

    total: int = Field(description="Total number of categories currently available.")
    categories: list[CategoryRead] = Field(
        default_factory=list,
        description="Detailed information for each available category.",
    )


class BillRead(BaseModel):
    """Representation of a recorded bill."""

    id: int
    amount: float
    type: str
    description: Optional[str] = Field(default=None, description="Description of the bill.")
    created_at: datetime = Field(description="Timestamp when the bill was created.")
    updated_at: datetime = Field(description="Timestamp when the bill was last updated.")
    category: Optional[CategoryRead] = Field(
        default=None, description="Category associated with the bill, if any."
    )

    class Config:
        from_attributes = True


class BillRecordResult(BaseModel):
    """Structured response returned after recording a bill."""

    message: str = Field(description="Human-readable confirmation message.")
    category_display: str = Field(
        description=(
            "Textual representation of the category used when recording the bill, "
            "including fallback information when the category is unknown."
        )
    )
    bill: BillRead = Field(description="Recorded bill instance returned by the backend.")


class BillBatchRecordResult(BaseModel):
    """Structured response returned after recording multiple bills."""

    message: str = Field(description="Summary message for the batch recording.")
    records: List[BillRecordResult] = Field(
        default_factory=list,
        description="Detailed result for each recorded bill.",
    )
