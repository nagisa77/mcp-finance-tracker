"""Pydantic 模型."""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .models import BillType


class CategoryRead(BaseModel):
    """分类输出模型."""

    id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class BillCreate(BaseModel):
    """账单创建输入模型."""

    amount: float = Field(..., gt=0, description="金额，必须为正数")
    type: BillType = Field(
        ..., description="账单类型，可选值为 income 或 expense"
    )
    category_id: Optional[int] = Field(
        default=None,
        description="分类 ID，未提供时记为未分类",
    )
    description: Optional[str] = Field(default=None, description="账单描述")

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("金额必须为正数")
        return value

    @field_validator("category_id")
    @classmethod
    def category_id_must_be_positive(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("分类 ID 必须为正整数")
        return value

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
    type: BillType
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


class CategoryExpenseBreakdown(BaseModel):
    """Representation of the total expense for a specific category."""

    category_id: Optional[int] = Field(
        default=None,
        description="Identifier of the category. None means uncategorised entries.",
    )
    category_name: str = Field(description="Display name of the category.")
    total_amount: float = Field(description="Total expense amount for the category.")
    percentage: float = Field(
        description=(
            "Contribution of this category to the total expense percentage (0-100)."
        )
    )


class ChartImage(BaseModel):
    """Base64 encoded chart image returned by the expense summary tool."""

    title: str = Field(description="Short label describing the chart.")
    mime_type: str = Field(
        default="image/png",
        description="MIME type of the encoded image content.",
        alias="mime_type",
    )
    base64_data: str = Field(
        description="Base64 encoded image bytes without data URL prefix.",
        alias="base64_data",
    )


class ExpenseSummaryCharts(BaseModel):
    """Collection of chart images illustrating the expense summary."""

    bar_chart: ChartImage = Field(
        description="Horizontal bar chart showing expense amount per category.",
        alias="bar_chart",
    )
    pie_chart: ChartImage = Field(
        description="Pie chart visualising the percentage contribution per category.",
        alias="pie_chart",
    )


class ExpenseSummaryResult(BaseModel):
    """Summary of expenses grouped by category for a given period."""

    period: Literal["day", "week", "month", "year"] = Field(
        description="The aggregation level used for the summary.",
    )
    reference: str = Field(
        description="Original user-supplied reference that defines the period.",
    )
    resolved_label: str = Field(
        description="Normalized representation of the requested period.",
    )
    start: datetime = Field(description="Inclusive start timestamp of the range.")
    end: datetime = Field(description="Exclusive end timestamp of the range.")
    total_expense: float = Field(description="Total expenses within the range.")
    category_breakdown: List[CategoryExpenseBreakdown] = Field(
        default_factory=list,
        description="Expenses for each category sorted by amount descending.",
    )
    charts: ExpenseSummaryCharts | None = Field(
        default=None,
        description="Optional chart visualisations encoded as base64 PNG images.",
    )


class BillExpenseDetail(BaseModel):
    """Detailed information for a single expense bill."""

    bill_id: int = Field(description="Unique identifier of the bill record.")
    amount: float = Field(description="Expense amount for the bill.")
    description: Optional[str] = Field(
        default=None, description="Optional description provided when recording."
    )
    created_at: datetime = Field(
        description="Timestamp representing when the bill was recorded.",
    )
    category_name: str = Field(description="Display name of the category.")


class CategoryExpenseDetailResult(BaseModel):
    """Summary of expenses for specific categories within a period."""

    period: Literal["day", "week", "month", "year"] = Field(
        description="The aggregation level used for the summary.",
    )
    reference: str = Field(
        description="Original user-supplied reference that defines the period.",
    )
    resolved_label: str = Field(
        description="Normalized representation of the requested period.",
    )
    start: datetime = Field(description="Inclusive start timestamp of the range.")
    end: datetime = Field(description="Exclusive end timestamp of the range.")
    category_ids: List[int] = Field(
        description="List of category identifiers included in this summary.",
    )
    selected_categories: List[CategoryRead] = Field(
        default_factory=list,
        description="Detailed information for the selected categories.",
    )
    total_expense: float = Field(
        description="Total expenses within the range for the selected categories.",
    )
    top_bills: List[BillExpenseDetail] = Field(
        default_factory=list,
        description="Top individual expense bills sorted by amount (up to 20 items).",
    )
