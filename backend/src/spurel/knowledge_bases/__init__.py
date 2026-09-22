"""Knowledge base domain."""

from spurel.knowledge_bases.domain import KnowledgeBase, KnowledgeBaseNameError
from spurel.knowledge_bases.ports import (
    KnowledgeBasePersistenceError,
    KnowledgeBaseRepository,
)
from spurel.knowledge_bases.service import KnowledgeBaseService

__all__ = [
    "KnowledgeBase",
    "KnowledgeBaseNameError",
    "KnowledgeBasePersistenceError",
    "KnowledgeBaseRepository",
    "KnowledgeBaseService",
]
