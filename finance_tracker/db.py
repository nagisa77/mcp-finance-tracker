"""Database configuration and initialization utilities."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_SQLITE_PATH = Path("data/finance.db")


def _build_database_url() -> str:
    """Return the database URL, defaulting to a local SQLite database."""
    import os

    url = os.getenv("DATABASE_URL")
    if url:
        return url
    DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE_PATH}"


DATABASE_URL = _build_database_url()

# For SQLite we need to disable same-thread check; leave kwargs empty otherwise.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


@contextmanager
def get_session() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(seed_defaults: bool = True) -> None:
    """Create database tables and optionally seed default categories."""
    from .seeding import seed_default_categories

    Base.metadata.create_all(bind=engine)
    if seed_defaults:
        with get_session() as session:
            seed_default_categories(session)
