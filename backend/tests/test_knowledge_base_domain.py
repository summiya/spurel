from datetime import UTC
from uuid import UUID

import pytest

from spurel.knowledge_bases import KnowledgeBase, KnowledgeBaseNameError


def test_create_knowledge_base() -> None:
    knowledge_base = KnowledgeBase.create("  Engineering Docs  ")

    assert isinstance(knowledge_base.id, UUID)
    assert knowledge_base.name == "Engineering Docs"
    assert knowledge_base.created_at.tzinfo is UTC


def test_create_knowledge_base_rejects_blank_name() -> None:
    with pytest.raises(KnowledgeBaseNameError):
        KnowledgeBase.create("   ")
