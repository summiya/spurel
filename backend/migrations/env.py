"""Alembic migration environment."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from spurel.db import Base
from spurel.documents import chunk_persistence, persistence as document_persistence
from spurel.embeddings import persistence as embedding_persistence
from spurel.knowledge_bases import persistence as knowledge_base_persistence
from spurel.retrieval import trace_persistence

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

_ = document_persistence.DocumentRecord
_ = embedding_persistence.ChunkEmbeddingRecord
_ = chunk_persistence.DocumentChunkRecord
_ = knowledge_base_persistence.KnowledgeBaseRecord
_ = trace_persistence.RetrievalTraceRecord
_ = trace_persistence.RetrievalTraceResultRecord

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    """Run migrations using a synchronous connection facade."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and execute migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
