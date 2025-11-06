"""Time range utilities for the MCP server."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal


def parse_period(
    period: Literal["day", "week", "month", "year"],
    reference: str,
) -> tuple[datetime, datetime, str]:
    """Convert a period and reference string into a start/end datetime and label."""

    ref = reference.strip()
    if not ref:
        raise ValueError("请提供用于确定时间范围的参考值。")

    if period == "day":
        try:
            target_date = datetime.strptime(ref, "%Y-%m-%d").date()
        except ValueError as exc:  # noqa: TRY003
            raise ValueError("日期格式错误，应为 YYYY-MM-DD。") from exc
        start = datetime.combine(target_date, time.min)
        end = start + timedelta(days=1)
        label = target_date.strftime("%Y-%m-%d")
    elif period == "week":
        try:
            year_part, week_part = ref.split("-W", maxsplit=1)
            target_year = int(year_part)
            target_week = int(week_part)
            target_date = date.fromisocalendar(target_year, target_week, 1)
        except ValueError as exc:  # noqa: TRY003
            raise ValueError("周格式错误，应为 YYYY-Www，例如 2024-W09。") from exc
        start = datetime.combine(target_date, time.min)
        end = start + timedelta(days=7)
        label = f"{target_year:04d}-W{target_week:02d}"
    elif period == "month":
        try:
            target_date = datetime.strptime(ref, "%Y-%m").date().replace(day=1)
        except ValueError as exc:  # noqa: TRY003
            raise ValueError("月份格式错误，应为 YYYY-MM。") from exc
        start = datetime.combine(target_date, time.min)
        next_month_base = target_date.replace(day=28) + timedelta(days=4)
        next_month = next_month_base.replace(day=1)
        end = datetime.combine(next_month, time.min)
        label = target_date.strftime("%Y-%m")
    elif period == "year":
        try:
            target_year = int(ref)
        except ValueError as exc:  # noqa: TRY003
            raise ValueError("年份格式错误，应为 YYYY。") from exc
        start_date = date(target_year, 1, 1)
        start = datetime.combine(start_date, time.min)
        end = datetime.combine(date(target_year + 1, 1, 1), time.min)
        label = f"{target_year:04d}"
    else:  # pragma: no cover - 类型系统保证
        raise ValueError("不支持的统计粒度。")

    return start, end, label


def validate_granularity(
    period: Literal["year", "month", "week"],
    granularity: Literal["month", "week", "day"],
) -> None:
    """Ensure the requested granularity is valid for the given period."""

    allowed_map: dict[str, set[str]] = {
        "year": {"month", "week", "day"},
        "month": {"week", "day"},
        "week": {"day"},
    }

    allowed = allowed_map.get(period)
    if allowed is None:
        raise ValueError("不支持的统计周期，请选择年、月或周。")

    if granularity not in allowed:
        raise ValueError("颗粒度必须小于周期，请选择更细的颗粒度。")
