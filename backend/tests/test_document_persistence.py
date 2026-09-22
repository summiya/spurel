from sqlalchemy import CheckConstraint
from uuid import uuid4

from spurel.documents import Document
from spurel.documents.persistence import DocumentRecord


def test_document_record_round_trip() -> None:
    document = Document.create(
        knowledge_base_id=uuid4(),
        filename="architecture.md",
        media_type="text/markdown",
        size_bytes=1024,
    )

    record = DocumentRecord.from_domain(document)
    restored = record.to_domain()

    assert restored == document


def test_document_table_shape() -> None:
    table = DocumentRecord.__table__

    assert table.name == "documents"
    assert set(table.columns.keys()) == {
        "id",
        "knowledge_base_id",
        "filename",
        "media_type",
        "size_bytes",
        "created_at",
    }
    assert table.primary_key.columns.keys() == ["id"]


def test_document_foreign_key_cascades_with_knowledge_base() -> None:
    foreign_key = next(iter(DocumentRecord.__table__.c.knowledge_base_id.foreign_keys))

    assert foreign_key.target_fullname == "knowledge_bases.id"
    assert foreign_key.ondelete == "CASCADE"


def test_document_table_has_defense_in_depth_constraints() -> None:
    constraints = {
        constraint.name
        for constraint in DocumentRecord.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints == {
        "ck_documents_size_bytes_bounds",
        "ck_documents_supported_media_type",
    }


def test_document_listing_index_matches_access_pattern() -> None:
    index = next(
        index
        for index in DocumentRecord.__table__.indexes
        if index.name == "ix_documents_knowledge_base_created_id"
    )

    assert [column.name for column in index.columns] == [
        "knowledge_base_id",
        "created_at",
        "id",
    ]
