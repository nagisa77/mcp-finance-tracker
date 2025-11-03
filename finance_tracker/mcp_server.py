"""Finance tracker MCP tool implementation."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP, Resource

from .db import init_db
from .repository import (
    Category,
    create_category,
    get_category_by_name,
    list_categories,
    record_transaction,
)

app = FastMCP("finance-tracker")


@app.on_startup()
def startup() -> None:
    """Initialise database schema when the MCP server starts."""
    init_db()


@app.tool()
def list_category_tool() -> List[Dict[str, Any]]:
    """List all available categories with descriptions."""
    categories = list_categories()
    return [
        {
            "id": category.id,
            "name": category.name,
            "description": category.description or "",
        }
        for category in categories
    ]


@app.tool()
def record_transaction_tool(
    *,
    amount: str,
    category_name: str,
    description: str | None = None,
    create_category_if_missing: bool = False,
) -> Dict[str, Any]:
    """Record a transaction in the ledger.

    Args:
        amount: A decimal number represented as a string. Use negative values for expenses
            and positive values for income.
        category_name: The target category. The tool will optionally create it if missing.
        description: Optional description for the transaction.
        create_category_if_missing: When True, a missing category will be created automatically.
    """

    try:
        parsed_amount = Decimal(amount)
    except (InvalidOperation, TypeError) as exc:  # pragma: no cover - defensive
        raise ValueError("Amount must be a valid decimal value") from exc

    category: Category | None = get_category_by_name(category_name)
    if category is None:
        if not create_category_if_missing:
            raise ValueError(f"Category '{category_name}' does not exist")
        category = create_category(category_name, description=None)

    transaction = record_transaction(
        amount=float(parsed_amount),
        category_id=category.id,
        description=description,
    )
    return {
        "id": transaction.id,
        "amount": transaction.amount,
        "category": {
            "id": transaction.category.id,
            "name": transaction.category.name,
            "description": transaction.category.description,
        },
        "description": transaction.description,
        "created_at": transaction.created_at,
    }


@app.list_resources()
def resources() -> List[Resource]:
    """Expose a single resource representing all categories."""
    categories = list_categories()
    content = "\n".join(
        f"- {category.name}: {category.description or '无描述'}" for category in categories
    )
    return [
        Resource(
            uri="finance-tracker://categories",
            description="Current list of finance categories",
            mime_type="text/markdown",
            text=f"## Categories\n{content if content else 'No categories have been defined yet.'}",
        )
    ]


if __name__ == "__main__":
    app.run()
