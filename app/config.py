"""Application configuration handling."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the finance tracker service."""

    db_host: str = os.environ.get("DB_HOST", "mysql")
    db_port: int = int(os.environ.get("DB_PORT", "3306"))
    db_user: str = os.environ.get("DB_USER", "finance")
    db_password: str = os.environ.get("DB_PASSWORD", "financepass")
    db_name: str = os.environ.get("DB_NAME", "finance_tracker")


settings = Settings()
