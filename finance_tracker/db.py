"""Database utilities for the finance tracker service."""
from __future__ import annotations

import contextlib
from typing import Generator

import mysql.connector
from mysql.connector import MySQLConnection

from .config import settings


CREATE_DATABASE_SQL = "CREATE DATABASE IF NOT EXISTS `{}`".format(settings.db_name)

CREATE_CATEGORIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

CREATE_TRANSACTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    amount DECIMAL(12, 2) NOT NULL,
    category_id INT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transactions_category FOREIGN KEY (category_id)
        REFERENCES categories(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


@contextlib.contextmanager
def mysql_connection(*, use_database: bool = True) -> Generator[MySQLConnection, None, None]:
    """Yield a configured MySQL connection."""

    connect_kwargs = {
        "host": settings.db_host,
        "port": settings.db_port,
        "user": settings.db_user,
        "password": settings.db_password,
    }
    if use_database:
        connect_kwargs["database"] = settings.db_name
    connection = mysql.connector.connect(**connect_kwargs)
    try:
        yield connection
    finally:
        connection.close()


def init_db() -> None:
    """Initialise the finance tracking database and tables."""

    # Ensure the database exists
    with mysql_connection(use_database=False) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_DATABASE_SQL)
        connection.commit()

    # Ensure the tables exist
    with mysql_connection(use_database=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_CATEGORIES_TABLE_SQL)
            cursor.execute(CREATE_TRANSACTIONS_TABLE_SQL)
        connection.commit()
