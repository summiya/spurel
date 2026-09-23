from datetime import UTC
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, UniqueConstraint

from spurel.embeddings.chunk import ChunkEmbedding
from spurel.embeddings.domain import EmbeddingVector
from spurel.embeddings.persistence import ChunkEmbeddingRecord


def test_chunk_embedding_record_round_trip() -> None:
    chunk_id = uuid4()
    embedding = ChunkEmbedding.create(
        chunk_id=chunk_id,
        provider=" OpenAI ",
        model="text-embedding-example",
        vector=EmbeddingVector.create(
            [0.1, 0.2, 0.3],
            expected_dimensions=3,
        ),
    )

    record = ChunkEmbeddingRecord.from_domain(embedding)
    restored = record.to_domain()

    assert isinstance(record.id, UUID)
    assert restored == embedding
    assert restored.provider == "openai"
    assert restored.created_at.tzinfo is UTC


def test_chunk_embedding_uses_dimension_flexible_pgvector_column() -> None:
    column_type = ChunkEmbeddingRecord.__table__.c.embedding.type

    assert isinstance(column_type, Vector)
    assert column_type.dim is None


def test_chunk_embedding_foreign_key_cascades_with_chunk() -> None:
    foreign_key = next(
        iter(ChunkEmbeddingRecord.__table__.c.chunk_id.foreign_keys)
    )

    assert foreign_key.target_fullname == "document_chunks.id"
    assert foreign_key.ondelete == "CASCADE"


def test_chunk_embedding_space_is_unique_per_chunk() -> None:
    unique = next(
        constraint
        for constraint in ChunkEmbeddingRecord.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_chunk_embeddings_chunk_space"
    )

    assert [column.name for column in unique.columns] == [
        "chunk_id",
        "provider",
        "model",
        "dimensions",
    ]


def test_chunk_embedding_has_dimension_integrity_checks() -> None:
    constraints = {
        constraint.name
        for constraint in ChunkEmbeddingRecord.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert {
        "ck_chunk_embeddings_dimension_bounds",
        "ck_chunk_embeddings_vector_dimensions",
    }.issubset(constraints)


def test_chunk_embedding_space_index_matches_future_retrieval_filter() -> None:
    index = next(
        index
        for index in ChunkEmbeddingRecord.__table__.indexes
        if index.name == "ix_chunk_embeddings_space_chunk"
    )

    assert [column.name for column in index.columns] == [
        "provider",
        "model",
        "dimensions",
        "chunk_id",
    ]
