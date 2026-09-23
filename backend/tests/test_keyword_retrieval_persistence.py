from sqlalchemy.schema import Computed

from spurel.documents.chunk_persistence import DocumentChunkRecord


def test_document_chunks_have_stored_search_vector() -> None:
    column = DocumentChunkRecord.__table__.c.search_vector

    assert isinstance(column.computed, Computed)
    assert column.computed.persisted is True
    assert "to_tsvector" in str(column.computed.sqltext)
    assert "english" in str(column.computed.sqltext)


def test_document_chunks_have_gin_search_index() -> None:
    index = next(
        index
        for index in DocumentChunkRecord.__table__.indexes
        if index.name == "ix_document_chunks_search_vector"
    )

    assert [column.name for column in index.columns] == ["search_vector"]
    assert index.dialect_options["postgresql"]["using"] == "gin"
