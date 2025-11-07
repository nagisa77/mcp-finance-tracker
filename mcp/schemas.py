"""Pydantic 模型."""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .models import BillType, CategoryType


class CategoryRead(BaseModel):
    """分类输出模型."""

    id: int
    user_id: str
    name: str
    description: Optional[str] = None
    color: str
    type: CategoryType

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
    user_id: str
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
    color: Optional[str] = Field(
        default=None, description="Display color associated with the category."
    )


class ChartImage(BaseModel):
    """Chart image metadata returned by the expense summary tool."""

    title: str = Field(description="Short label describing the chart.")
    mime_type: str = Field(
        default="image/png",
        description="MIME type of the stored image content.",
        alias="mime_type",
    )
    image_url: str = Field(
        description="Publicly accessible URL pointing to the chart image.",
        alias="image_url",
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
    charts: List[ChartImage] = Field(
        default_factory=list,
        description="Optional chart visualisations hosted remotely (e.g. on COS).",
    )


class ExpenseComparisonSnapshot(BaseModel):
    """Expense statistics for a specific period used in comparisons."""

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


class ExpenseComparisonResult(BaseModel):
    """Comparison of expenses between two periods."""

    period: Literal["day", "week", "month", "year"] = Field(
        description="The aggregation level used for the comparison.",
    )
    first: ExpenseComparisonSnapshot = Field(
        description="Statistics for the first period provided in the comparison.",
    )
    second: ExpenseComparisonSnapshot = Field(
        description="Statistics for the second period provided in the comparison.",
    )
    charts: List[ChartImage] = Field(
        default_factory=list,
        description="Optional comparison charts hosted remotely (e.g. on COS).",
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


class ExpenseTimelineBucket(BaseModel):
    """Aggregated expense statistics for a specific time bucket."""

    label: str = Field(description="Canonical label representing the bucket range.")
    display_label: str = Field(
        description="Human friendly label used when rendering charts.",
    )
    start: datetime = Field(description="Inclusive start timestamp for the bucket.")
    end: datetime = Field(description="Exclusive end timestamp for the bucket.")
    total_expense: float = Field(description="Total expenses that fall into the bucket.")


class ExpenseTimelineSnapshot(BaseModel):
    """Time-series expense snapshot for a specific period and category selection."""

    period: Literal["year", "month", "week"] = Field(
        description="The primary time period that defines the snapshot.",
    )
    reference: str = Field(
        description="User supplied reference string used to resolve the time period.",
    )
    resolved_label: str = Field(
        description="Human readable representation of the requested period.",
    )
    start: datetime = Field(description="Inclusive start timestamp of the period.")
    end: datetime = Field(description="Exclusive end timestamp of the period.")
    granularity: Literal["month", "week", "day"] = Field(
        description="Granularity used for aggregating expenses within the period.",
    )
    category_ids: List[int] = Field(
        description="Category identifiers included in the snapshot (empty for all).",
    )
    selected_categories: List[CategoryRead] = Field(
        default_factory=list,
        description="Detailed information about the selected categories.",
    )
    total_expense: float = Field(
        description="Total expense amount captured by this snapshot.",
    )
    buckets: List[ExpenseTimelineBucket] = Field(
        default_factory=list,
        description="Aggregated expense buckets ordered by time.",
    )


class ExpenseTimelineResult(BaseModel):
    """Response model returned by the expense timeline tool."""

    period: Literal["year", "month", "week"] = Field(
        description="The period requested when generating the timeline.",
    )
    granularity: Literal["month", "week", "day"] = Field(
        description="Granularity used for aggregating expenses within each bucket.",
    )
    primary: ExpenseTimelineSnapshot = Field(
        description="Snapshot representing the requested period.",
    )
    comparison: Optional[ExpenseTimelineSnapshot] = Field(
        default=None,
        description="Optional snapshot for the comparison period if provided.",
    )
    charts: List[ChartImage] = Field(
        default_factory=list,
        description="Optional chart images hosted remotely (e.g. on COS).",
    )
