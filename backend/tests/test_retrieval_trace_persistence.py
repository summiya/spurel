from uuid import uuid4

from spurel.retrieval.trace_persistence import (
    RetrievalTraceRecord,
    RetrievalTraceResultRecord,
)
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceResult,
)


def test_trace_persistence_keeps_result_snapshots_independent_of_live_chunks() -> None:
    chunk_id = uuid4()
    document_id = uuid4()
    result = RetrievalTraceResult(
        rank=1,
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=3,
        text="snapshot text",
        start_offset=100,
        end_offset=113,
        cosine_similarity=0.91,
        keyword_score=0.72,
        rrf_score=0.0325,
        vector_rank=1,
        keyword_rank=2,
    )
    trace = RetrievalTrace.create(
        knowledge_base_id=uuid4(),
        mode=RetrievalTraceMode.HYBRID,
        query="query",
        top_k=10,
        candidate_k=50,
        rrf_k=60,
        duration_ms=15.5,
        embedding_provider="openai",
        embedding_model="model",
        embedding_dimensions=1536,
        results=(result,),
    )

    trace_record = RetrievalTraceRecord.from_domain(trace)
    result_record = RetrievalTraceResultRecord.from_domain(
        trace_id=trace.id,
        result=result,
    )

    assert trace_record.id == trace.id
    assert trace_record.mode == "hybrid"
    assert result_record.trace_id == trace.id
    assert result_record.chunk_id == chunk_id
    assert result_record.document_id == document_id
    assert result_record.to_domain() == result


def test_trace_result_snapshot_ids_have_no_live_chunk_foreign_keys() -> None:
    table = RetrievalTraceResultRecord.__table__

    chunk_foreign_keys = list(table.c.chunk_id.foreign_keys)
    document_foreign_keys = list(table.c.document_id.foreign_keys)

    assert chunk_foreign_keys == []
    assert document_foreign_keys == []


def test_trace_tables_define_experiment_lookup_indexes() -> None:
    trace_index = next(
        index
        for index in RetrievalTraceRecord.__table__.indexes
        if index.name == "ix_retrieval_traces_knowledge_base_created_id"
    )
    result_index = next(
        index
        for index in RetrievalTraceResultRecord.__table__.indexes
        if index.name == "ix_retrieval_trace_results_trace_rank"
    )

    assert [column.name for column in trace_index.columns] == [
        "knowledge_base_id",
        "created_at",
        "id",
    ]
    assert [column.name for column in result_index.columns] == [
        "trace_id",
        "rank",
    ]
