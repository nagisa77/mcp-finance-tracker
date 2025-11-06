"""Helpers related to category lookups and normalization."""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from ..crud import get_category_by_id
from ..models import Category


def resolve_category(
    session: Session, category_id: int | None, user_id: str
) -> tuple[Category | None, str]:
    """Resolve a category by id and return the display name."""

    category_obj: Category | None = None
    category_display = "未分类"
    if category_id is not None:
        category_obj = get_category_by_id(session, category_id, user_id)
        if category_obj is not None:
            category_display = category_obj.name
        else:
            category_display = f"未知分类：{category_id}"
    return category_obj, category_display


def unique_category_ids(category_ids: Iterable[int]) -> list[int]:
    """Return unique category ids while preserving order."""

    seen: dict[int, None] = {}
    for cid in category_ids:
        if cid not in seen:
            seen[cid] = None
    return list(seen.keys())
