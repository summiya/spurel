"""Dependency wiring for knowledge base HTTP endpoints."""

from spurel.db import async_session_factory
from spurel.knowledge_bases.service import KnowledgeBaseService
from spurel.knowledge_bases.sqlalchemy_repository import (
    SqlAlchemyKnowledgeBaseRepository,
)


def get_knowledge_base_service() -> KnowledgeBaseService:
    """Build the knowledge base application service."""
    repository = SqlAlchemyKnowledgeBaseRepository(async_session_factory)
    return KnowledgeBaseService(repository)
