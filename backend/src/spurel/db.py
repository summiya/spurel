"""Database primitives for Spurel."""

import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DEFAULT_DATABASE_URL = "postgresql+asyncpg://spurel:spurel@localhost:5432/spurel"


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def get_database_url() -> str:
    """Return the configured database URL."""
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """Create the application async SQLAlchemy engine."""
    return create_async_engine(database_url or get_database_url())


engine = create_engine()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
