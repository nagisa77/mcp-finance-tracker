"""MCP server exposing finance tracking utilities."""
from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation

from mcp.server.fastmcp import FastMCP

from .crud import create_transaction, get_category_by_name, list_categories
from .db import get_session, init_db

mcp = FastMCP("finance-tracker")


@mcp.on_startup
async def _on_startup() -> None:
    """Initialize the database when the server starts."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, init_db)


@mcp.tool()
def list_finance_categories() -> str:
    """返回当前记账分类及其描述。"""
    with get_session() as session:
        categories = list_categories(session)

    if not categories:
        return "当前还没有分类，请先在数据库中创建。"

    lines = ["当前分类列表："]
    for category in categories:
        description = category.description or "无描述"
        lines.append(f"- {category.name}: {description}")
    return "\n".join(lines)


@mcp.tool()
def record_bill(amount: float, category: str, description: str = "") -> str:
    """记录一笔新的账单。支出使用负数，收入使用正数金额。"""
    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("金额格式不正确，请输入数字。") from exc

    with get_session() as session:
        category_obj = get_category_by_name(session, category)
        if category_obj is None:
            available = ", ".join(cat.name for cat in list_categories(session)) or "无可用分类"
            raise ValueError(f"未找到分类：{category}。可用分类：{available}")

        transaction = create_transaction(
            session,
            amount=decimal_amount,
            category=category_obj,
            description=description,
        )

    sign = "收入" if transaction.amount >= 0 else "支出"
    return (
        f"已记录{sign}账单：金额 {transaction.amount}，分类 {category_obj.name}"
        + (f"，备注：{description}" if description else "")
    )


def run() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    run()
