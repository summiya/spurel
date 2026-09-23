from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, UniqueConstraint

from spurel.documents.chunk_persistence import DocumentChunkRecord
from spurel.documents.chunking import DocumentChunk


def test_document_chunk_record_round_trip() -> None:
    document_id = uuid4()
    chunk = DocumentChunk(
        index=3,
        text="retrieval context",
        start_offset=100,
        end_offset=117,
    )

    record = DocumentChunkRecord.from_domain(
        document_id=document_id,
        chunk=chunk,
    )
    restored = record.to_domain()

    assert isinstance(record.id, UUID)
    assert record.document_id == document_id
    assert restored == chunk


def test_document_chunk_foreign_key_cascades_with_document() -> None:
    foreign_key = next(
        iter(DocumentChunkRecord.__table__.c.document_id.foreign_keys)
    )

    assert foreign_key.target_fullname == "documents.id"
    assert foreign_key.ondelete == "CASCADE"


def test_document_chunk_table_has_defense_in_depth_constraints() -> None:
    constraints = {
        constraint.name
        for constraint in DocumentChunkRecord.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints == {
        "ck_document_chunks_index_bounds",
        "ck_document_chunks_offset_order",
        "ck_document_chunks_offset_span",
        "ck_document_chunks_text_length",
    }


def test_document_chunk_index_is_unique_per_document() -> None:
    unique = next(
        constraint
        for constraint in DocumentChunkRecord.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_document_chunks_document_index"
    )

    assert [column.name for column in unique.columns] == [
        "document_id",
        "chunk_index",
    ]


def test_document_chunk_offset_index_matches_inspection_access_pattern() -> None:
    index = next(
        index
        for index in DocumentChunkRecord.__table__.indexes
        if index.name == "ix_document_chunks_document_offsets"
    )

    assert [column.name for column in index.columns] == [
        "document_id",
        "start_offset",
        "end_offset",
    ]
