"""Data access layer for categories and transactions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .db import mysql_connection


@dataclass
class Category:
    id: int
    name: str
    description: Optional[str]


@dataclass
class Transaction:
    id: int
    amount: float
    category: Category
    description: Optional[str]
    created_at: str


def list_categories() -> List[Category]:
    """Return all categories in the system."""
    with mysql_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id, name, description FROM categories ORDER BY name ASC")
            rows = cursor.fetchall()
    return [Category(**row) for row in rows]


def get_category_by_name(name: str) -> Optional[Category]:
    """Fetch a category by its unique name."""
    with mysql_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT id, name, description FROM categories WHERE name = %s",
                (name,),
            )
            row = cursor.fetchone()
    return Category(**row) if row else None


def create_category(name: str, description: Optional[str]) -> Category:
    """Create a new category if it does not already exist."""
    with mysql_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(
                "INSERT INTO categories (name, description) VALUES (%s, %s)",
                (name, description),
            )
            connection.commit()
            category_id = cursor.lastrowid
            cursor.execute(
                "SELECT id, name, description FROM categories WHERE id = %s",
                (category_id,),
            )
            row = cursor.fetchone()
    return Category(**row)


def record_transaction(amount: float, category_id: int, description: Optional[str]) -> Transaction:
    """Create a new transaction record."""
    with mysql_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(
                "INSERT INTO transactions (amount, category_id, description) VALUES (%s, %s, %s)",
                (amount, category_id, description),
            )
            connection.commit()
            transaction_id = cursor.lastrowid
            cursor.execute(
                """
                SELECT t.id, t.amount, t.description, t.created_at,
                       c.id AS category_id, c.name AS category_name, c.description AS category_description
                FROM transactions AS t
                JOIN categories AS c ON t.category_id = c.id
                WHERE t.id = %s
                """,
                (transaction_id,),
            )
            row = cursor.fetchone()
    category = Category(
        id=row["category_id"],
        name=row["category_name"],
        description=row.get("category_description"),
    )
    return Transaction(
        id=row["id"],
        amount=float(row["amount"]),
        category=category,
        description=row.get("description"),
        created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
    )
