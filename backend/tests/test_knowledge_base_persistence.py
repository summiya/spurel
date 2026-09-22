from spurel.knowledge_bases import KnowledgeBase
from spurel.knowledge_bases.persistence import KnowledgeBaseRecord


def test_knowledge_base_record_round_trip() -> None:
    knowledge_base = KnowledgeBase.create("Engineering Docs")

    record = KnowledgeBaseRecord.from_domain(knowledge_base)
    restored = record.to_domain()

    assert restored == knowledge_base


def test_knowledge_base_table_shape() -> None:
    table = KnowledgeBaseRecord.__table__

    assert table.name == "knowledge_bases"
    assert set(table.columns.keys()) == {"id", "name", "created_at"}
    assert table.primary_key.columns.keys() == ["id"]
