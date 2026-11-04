"""PostgreSQL integration tests for Spurel's real repositories and application flows.

These tests never call OpenAI. They run only against a dedicated *_test database
with Alembic migrations already applied.
"""

import asyncio
import hashlib
import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from spurel.documents.chunk_inspector import ChunkInspectorService
from spurel.documents.chunk_pipeline import DocumentChunkPipeline
from spurel.documents.chunk_ports import (
    DocumentChunkPersistenceError,
    DocumentChunkVersionIncompleteError,
    DocumentProcessingConflictError,
)
from spurel.documents.chunk_service import DocumentChunkService
from spurel.documents.chunk_versions_persistence import DocumentChunkVersionRecord
from spurel.documents.chunking import DocumentChunk
from spurel.documents.dependencies import (
    get_chunk_inspector_service,
    get_document_upload_service,
    get_document_version_service,
)
from spurel.documents.domain import DocumentMediaType
from spurel.documents.ingestion_service import DocumentIngestionService
from spurel.documents.persistence import DocumentRecord
from spurel.documents.processing import DocumentProcessingService
from spurel.documents.processing_dependencies import get_document_processing_service
from spurel.documents.sqlalchemy_chunk_inspector_repository import (
    SqlAlchemyChunkInspectorRepository,
)
from spurel.documents.sqlalchemy_chunk_repository import SqlAlchemyDocumentChunkRepository
from spurel.documents.sqlalchemy_repository import SqlAlchemyDocumentRepository
from spurel.documents.sqlalchemy_version_repository import SqlAlchemyDocumentVersionRepository
from spurel.documents.storage import document_object_key
from spurel.documents.upload_service import DocumentUploadService
from spurel.documents.versions import DocumentVersionService
from spurel.embeddings.chunk import ChunkEmbedding
from spurel.embeddings.domain import EmbeddingBatch, EmbeddingProviderError, EmbeddingVector
from spurel.embeddings.pipeline import DocumentEmbeddingPipeline
from spurel.embeddings.service import ChunkEmbeddingService
from spurel.embeddings.sqlalchemy_repository import SqlAlchemyChunkEmbeddingRepository
from spurel.evaluation_datasets.baseline_domain import EvaluationBaselineConfiguration
from spurel.evaluation_datasets.baseline_service import EvaluationBaselineService
from spurel.evaluation_datasets.dependencies import (
    get_evaluation_dataset_service,
    get_keyword_dataset_evaluation_service,
)
from spurel.evaluation_datasets.execution import (
    DatasetEvaluationExecutionService,
    DatasetEvaluationMode,
    KeywordDatasetRetriever,
)
from spurel.evaluation_datasets.judgment_integrity import (
    EvaluationJudgmentIssueReason,
)
from spurel.evaluation_datasets.ports import (
    EvaluationJudgmentInvalidError,
    EvaluationJudgmentStaleError,
)
from spurel.evaluation_datasets.quality_gate import (
    EvaluationQualityGateService,
    EvaluationQualityGateStatus,
    EvaluationQualityGateThresholds,
)
from spurel.evaluation_datasets.run_comparison import EvaluationRunComparisonService
from spurel.evaluation_datasets.run_service import (
    EvaluationRunService,
    PersistedDatasetEvaluationService,
)
from spurel.evaluation_datasets.service import EvaluationDatasetService
from spurel.evaluation_datasets.sqlalchemy_baseline_repository import (
    SqlAlchemyEvaluationBaselineRepository,
)
from spurel.evaluation_datasets.sqlalchemy_repository import SqlAlchemyEvaluationDatasetRepository
from spurel.evaluation_datasets.sqlalchemy_run_repository import SqlAlchemyEvaluationRunRepository
from spurel.infrastructure.chunking.fixed import FixedSizeDocumentChunker
from spurel.infrastructure.parsing.text import TextDocumentParser
from spurel.infrastructure.storage.local import LocalDocumentBlobStorage
from spurel.knowledge_bases.dependencies import get_knowledge_base_service
from spurel.knowledge_bases.persistence import KnowledgeBaseRecord
from spurel.knowledge_bases.service import KnowledgeBaseService
from spurel.knowledge_bases.sqlalchemy_repository import SqlAlchemyKnowledgeBaseRepository
from spurel.main import create_app
from spurel.retrieval.dependencies import (
    get_retrieval_trace_service,
    get_traced_hybrid_retrieval_service,
    get_traced_keyword_retrieval_service,
    get_traced_vector_retrieval_service,
)
from spurel.retrieval.evaluation import RelevanceJudgment
from spurel.retrieval.hnsw import (
    HnswBenchmarkOptions,
    HnswIndexOptions,
    benchmark_index,
    build_index,
)
from spurel.retrieval.hybrid import HybridRetrievalService
from spurel.retrieval.keyword_service import KeywordRetrievalService
from spurel.retrieval.service import VectorRetrievalService
from spurel.retrieval.sqlalchemy_keyword_repository import SqlAlchemyKeywordRetrievalRepository
from spurel.retrieval.sqlalchemy_repository import SqlAlchemyVectorRetrievalRepository
from spurel.retrieval.sqlalchemy_trace_repository import SqlAlchemyRetrievalTraceRepository
from spurel.retrieval.trace_service import RetrievalTraceService
from spurel.retrieval.traced import (
    TracedHybridRetrievalService,
    TracedKeywordRetrievalService,
    TracedVectorRetrievalService,
)

pytestmark = pytest.mark.postgres

_TEST_TOKEN = "spurel-integration-test-token-with-at-least-32-characters"


@pytest.fixture
def postgres_url() -> str:
    """Never run database-writing tests against a non-test database."""
    url = os.getenv("SPUREL_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SPUREL_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    parsed = make_url(url)
    if parsed.drivername != "postgresql+asyncpg" or not (
        parsed.database and parsed.database.endswith("_test")
    ):
        pytest.fail("Integration tests require a postgresql+asyncpg database ending in _test")
    return url


@dataclass
class _Database:
    sessions: async_sessionmaker[AsyncSession]
    created_kb_ids: list[UUID] = field(default_factory=list)

    async def new_knowledge_base(self, name: str) -> UUID:
        service = KnowledgeBaseService(SqlAlchemyKnowledgeBaseRepository(self.sessions))
        knowledge_base = await service.create(name)
        self.created_kb_ids.append(knowledge_base.id)
        return knowledge_base.id


@asynccontextmanager
async def _isolated_database(url: str) -> AsyncIterator[_Database]:
    """Use one engine per event loop and clean up only our own KBs via FK cascades."""
    engine = create_async_engine(url)
    database = _Database(sessions=async_sessionmaker(engine, expire_on_commit=False))
    try:
        yield database
    finally:
        try:
            if database.created_kb_ids:
                async with database.sessions() as session:
                    async with session.begin():
                        await session.execute(
                            delete(KnowledgeBaseRecord).where(
                                KnowledgeBaseRecord.id.in_(database.created_kb_ids)
                            )
                        )
        finally:
            await engine.dispose()


class _DeterministicEmbeddings:
    """Small 3D vectors to test pgvector without an external provider."""

    provider = "integration"
    model = "fixture-3d"
    dimensions = 3

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        vectors = []
        for text in texts:
            normalized = text.lower()
            if "refund" in normalized:
                vectors.append([1.0, 0.0, 0.0])
            elif "backup" in normalized:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return EmbeddingBatch.create(
            vectors=vectors,
            input_count=len(texts),
            model=self.model,
            dimensions=self.dimensions,
        )


def _processor(
    database: _Database,
    storage: LocalDocumentBlobStorage,
    provider: _DeterministicEmbeddings,
    chunk_size: int = 512,
    batch_size: int = 256,
) -> DocumentProcessingService:
    documents = SqlAlchemyDocumentRepository(database.sessions)
    chunks = SqlAlchemyDocumentChunkRepository(database.sessions)
    embeddings = SqlAlchemyChunkEmbeddingRepository(database.sessions)
    parser = TextDocumentParser()
    chunk_pipeline = DocumentChunkPipeline(
        ingestion_service=DocumentIngestionService(
            repository=documents,
            storage=storage,
            parsers={DocumentMediaType.TEXT: parser, DocumentMediaType.MARKDOWN: parser},
        ),
        chunker=FixedSizeDocumentChunker(chunk_size=chunk_size, overlap=0),
        chunk_service=DocumentChunkService(chunks),
    )
    return DocumentProcessingService(
        chunk_pipeline=chunk_pipeline,
        embedding_pipeline=DocumentEmbeddingPipeline(
            chunk_reader=chunks,
            provider=provider,
            embedding_service=ChunkEmbeddingService(embeddings),
            batch_size=batch_size,
        ),
    )


async def _upload(
    database: _Database,
    storage: LocalDocumentBlobStorage,
    kb_id: UUID,
    text: str,
) -> UUID:
    content = text.encode("utf-8")

    async def content_chunks() -> AsyncIterator[bytes]:
        midpoint = len(content) // 2
        yield content[:midpoint]
        yield content[midpoint:]

    result = await DocumentUploadService(
        repository=SqlAlchemyDocumentRepository(database.sessions),
        storage=storage,
    ).upload(
        knowledge_base_id=kb_id,
        filename="policy.txt",
        media_type="text/plain",
        declared_size_bytes=len(content),
        chunks=content_chunks(),
    )
    assert result.sha256 == hashlib.sha256(content).hexdigest()
    return result.document.id


def _retrievers(database: _Database, provider: _DeterministicEmbeddings):
    vectors = VectorRetrievalService(
        provider=provider,
        repository=SqlAlchemyVectorRetrievalRepository(database.sessions),
    )
    keywords = KeywordRetrievalService(SqlAlchemyKeywordRetrievalRepository(database.sessions))
    hybrid = HybridRetrievalService(vector_retriever=vectors, keyword_retriever=keywords)
    traces = RetrievalTraceService(SqlAlchemyRetrievalTraceRepository(database.sessions))
    return vectors, keywords, hybrid, traces


def test_http_upload_process_retrieve_and_trace_with_kb_isolation(
    postgres_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_API_TOKEN", _TEST_TOKEN)
    asyncio.run(_http_upload_process_retrieve(postgres_url, tmp_path))


async def _http_upload_process_retrieve(postgres_url: str, tmp_path: Path) -> None:
    async with _isolated_database(postgres_url) as database:
        provider = _DeterministicEmbeddings()
        storage = LocalDocumentBlobStorage(tmp_path / "documents")
        vectors, keywords, hybrid, traces = _retrievers(database, provider)
        app = create_app()
        app.dependency_overrides[get_knowledge_base_service] = lambda: KnowledgeBaseService(
            SqlAlchemyKnowledgeBaseRepository(database.sessions)
        )
        app.dependency_overrides[get_document_upload_service] = lambda: DocumentUploadService(
            repository=SqlAlchemyDocumentRepository(database.sessions),
            storage=storage,
        )
        app.dependency_overrides[get_document_processing_service] = lambda: _processor(
            database, storage, provider
        )
        app.dependency_overrides[get_chunk_inspector_service] = lambda: ChunkInspectorService(
            SqlAlchemyChunkInspectorRepository(database.sessions)
        )
        app.dependency_overrides[get_traced_vector_retrieval_service] = lambda: (
            TracedVectorRetrievalService(
                retriever=vectors,
                trace_service=traces,
                embedding_provider=provider.provider,
                embedding_model=provider.model,
                embedding_dimensions=provider.dimensions,
            )
        )
        app.dependency_overrides[get_traced_keyword_retrieval_service] = lambda: (
            TracedKeywordRetrievalService(retriever=keywords, trace_service=traces)
        )
        app.dependency_overrides[get_traced_hybrid_retrieval_service] = lambda: (
            TracedHybridRetrievalService(
                retriever=hybrid,
                trace_service=traces,
                embedding_provider=provider.provider,
                embedding_model=provider.model,
                embedding_dimensions=provider.dimensions,
            )
        )
        app.dependency_overrides[get_retrieval_trace_service] = lambda: traces

        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/knowledge-bases")).status_code == 401

            kb_ids = []
            for name in ("Public policies", "Other tenant"):
                response = await client.post(
                    "/knowledge-bases", json={"name": name}, headers=headers
                )
                assert response.status_code == 201, response.text
                kb_id = UUID(response.json()["id"])
                database.created_kb_ids.append(kb_id)
                kb_ids.append(kb_id)
            public_kb, private_kb = kb_ids

            documents = (
                (public_kb, "refund.txt", b"Refund requests are accepted within thirty days."),
                (public_kb, "backup.txt", b"Backups are performed every hour."),
                (private_kb, "private.txt", b"Private refund approvals require a manager."),
            )
            uploaded_ids = []
            for kb_id, name, content in documents:
                response = await client.post(
                    f"/knowledge-bases/{kb_id}/documents",
                    files={"file": (name, content, "text/plain")},
                    headers=headers,
                )
                assert response.status_code == 201, response.text
                assert response.json()["sha256"] == hashlib.sha256(content).hexdigest()
                document_id = UUID(response.json()["id"])
                uploaded_ids.append(document_id)
                processed = await client.post(
                    f"/knowledge-bases/{kb_id}/documents/{document_id}/process",
                    headers=headers,
                )
                assert processed.status_code == 200, processed.text
                assert processed.json()["chunk_count"] == 1
                assert processed.json()["embedded_chunk_count"] == 1
                assert processed.json()["embedding_dimensions"] == 3

            for document_id in uploaded_ids[:2]:
                inspected = await client.get(
                    f"/knowledge-bases/{public_kb}/documents/{document_id}/chunks",
                    headers=headers,
                )
                assert inspected.status_code == 200, inspected.text
                assert len(inspected.json()["items"]) == 1
                assert inspected.json()["items"][0]["embedding_count"] == 1

            inaccessible = await client.get(
                f"/knowledge-bases/{public_kb}/documents/{uploaded_ids[2]}/chunks",
                headers=headers,
            )
            assert inaccessible.status_code == 200
            assert inaccessible.json()["items"] == []

            for mode in ("vector", "keyword", "hybrid"):
                payload = {"query": "refund", "top_k": 3}
                if mode == "hybrid":
                    payload.update(candidate_k=3, rrf_k=60)
                response = await client.post(
                    f"/knowledge-bases/{public_kb}/retrieval/{mode}",
                    json=payload,
                    headers=headers,
                )
                assert response.status_code == 200, response.text
                matches = response.json()["matches"]
                assert matches
                assert matches[0]["document_id"] == str(uploaded_ids[0])
                assert all(match["document_id"] != str(uploaded_ids[2]) for match in matches)

                trace_id = UUID(response.json()["trace_id"])
                persisted = await traces.get_by_id(knowledge_base_id=public_kb, trace_id=trace_id)
                assert persisted.results[0].document_id == uploaded_ids[0]
                assert persisted.mode.value == mode

            # SP-19: post-ranking filtering would incorrectly starve these results.
            # Every retrieval mode must apply document metadata within SQL.
            for mode in ("vector", "keyword", "hybrid"):
                request = {
                    "query": "refund",
                    "top_k": 3,
                    "filters": {
                        "document_ids": [str(uploaded_ids[0])],
                        "media_types": ["text/plain"],
                        "filename_contains": "REFUND",
                        "created_after": "2020-01-01T00:00:00Z",
                        "created_before": "2030-01-01T00:00:00Z",
                    },
                }
                if mode == "hybrid":
                    request.update(candidate_k=3, rrf_k=60)
                response = await client.post(
                    f"/knowledge-bases/{public_kb}/retrieval/{mode}",
                    json=request,
                    headers=headers,
                )
                assert response.status_code == 200, response.text
                assert response.json()["matches"]
                assert all(
                    match["document_id"] == str(uploaded_ids[0])
                    for match in response.json()["matches"]
                )
                saved = await traces.get_by_id(
                    knowledge_base_id=public_kb,
                    trace_id=UUID(response.json()["trace_id"]),
                )
                assert saved.metadata_filters is not None
                assert saved.metadata_filters.document_ids == (uploaded_ids[0],)
                assert saved.metadata_filters.filename_contains == "REFUND"

                # A document from another knowledge base cannot escape scope,
                # even when an otherwise valid document UUID is supplied.
                blocked = {**request, "filters": {"document_ids": [str(uploaded_ids[2])]}}
                excluded = await client.post(
                    f"/knowledge-bases/{public_kb}/retrieval/{mode}",
                    json=blocked,
                    headers=headers,
                )
                assert excluded.status_code == 200
                assert excluded.json()["matches"] == []

                # PDF is an allowed file type but none were indexed in this KB.
                incompatible = {**request, "filters": {"media_types": ["application/pdf"]}}
                excluded_type = await client.post(
                    f"/knowledge-bases/{public_kb}/retrieval/{mode}",
                    json=incompatible,
                    headers=headers,
                )
                assert excluded_type.status_code == 200
                assert excluded_type.json()["matches"] == []

            assert await traces.list_by_knowledge_base(knowledge_base_id=public_kb, limit=20)
            document = await SqlAlchemyDocumentRepository(database.sessions).get_by_id(
                knowledge_base_id=public_kb, document_id=uploaded_ids[0]
            )
            assert document is not None
            stored = await storage.get(object_key=document_object_key(document))
            assert stored == documents[0][2]


def test_persisted_dataset_runs_comparisons_and_baselines(
    postgres_url: str, tmp_path: Path
) -> None:
    asyncio.run(_evaluation_round_trip(postgres_url, tmp_path))


async def _evaluation_round_trip(postgres_url: str, tmp_path: Path) -> None:
    async with _isolated_database(postgres_url) as database:
        kb_id = await database.new_knowledge_base("Evaluation integration")
        storage = LocalDocumentBlobStorage(tmp_path / "evaluation")
        document_id = await _upload(
            database, storage, kb_id, "Refund requests are accepted within thirty days."
        )
        await _processor(database, storage, _DeterministicEmbeddings()).process(
            knowledge_base_id=kb_id, document_id=document_id
        )
        chunks = await SqlAlchemyDocumentChunkRepository(database.sessions).list_stored_by_document(
            document_id=document_id, limit=10, offset=0
        )
        assert len(chunks) == 1

        evaluation_repository = SqlAlchemyEvaluationDatasetRepository(database.sessions)
        datasets = EvaluationDatasetService(evaluation_repository)
        dataset = await datasets.create_dataset(
            knowledge_base_id=kb_id, name="Refund policy regression"
        )
        case = await datasets.add_case(
            knowledge_base_id=kb_id,
            dataset_id=dataset.id,
            query="refund",
            judgments=(RelevanceJudgment(chunk_id=chunks[0].id, relevance=3),),
        )
        stored_case = await datasets.get_case(
            knowledge_base_id=kb_id, dataset_id=dataset.id, case_id=case.id
        )
        assert stored_case.judgments == case.judgments

        runner = PersistedDatasetEvaluationService(
            executor=DatasetEvaluationExecutionService(
                repository=evaluation_repository,
                retriever=KeywordDatasetRetriever(
                    KeywordRetrievalService(SqlAlchemyKeywordRetrievalRepository(database.sessions))
                ),
                mode=DatasetEvaluationMode.KEYWORD,
            ),
            runs=EvaluationRunService(SqlAlchemyEvaluationRunRepository(database.sessions)),
        )
        first = await runner.run(knowledge_base_id=kb_id, dataset_id=dataset.id, top_k=1)
        second = await runner.run(knowledge_base_id=kb_id, dataset_id=dataset.id, top_k=1)
        assert first.mean_recall_at_k == 1.0
        assert first.mrr_at_k == 1.0

        runs = EvaluationRunService(SqlAlchemyEvaluationRunRepository(database.sessions))
        restored = await runs.get_by_id(
            knowledge_base_id=kb_id, dataset_id=dataset.id, run_id=first.id
        )
        assert restored.cases[0].case_id == case.id

        comparisons = EvaluationRunComparisonService(runs)
        comparison = await comparisons.compare(
            knowledge_base_id=kb_id,
            dataset_id=dataset.id,
            first_run_id=first.id,
            second_run_id=second.id,
        )
        assert comparison.aggregate_comparable
        assert comparison.mean_recall_delta == 0.0

        baseline_service = EvaluationBaselineService(
            repository=SqlAlchemyEvaluationBaselineRepository(database.sessions),
            runs=runs,
        )
        await baseline_service.promote(
            knowledge_base_id=kb_id, dataset_id=dataset.id, run_id=first.id
        )
        await baseline_service.promote(
            knowledge_base_id=kb_id, dataset_id=dataset.id, run_id=second.id
        )
        promoted = await baseline_service.resolve(
            knowledge_base_id=kb_id,
            dataset_id=dataset.id,
            configuration=EvaluationBaselineConfiguration.from_run(second),
        )
        assert promoted.run_id == second.id
        history = await baseline_service.list_history_by_dataset(
            knowledge_base_id=kb_id, dataset_id=dataset.id, limit=10
        )
        assert len(history) == 2
        assert {entry.run_id for entry in history} == {first.id, second.id}

        gate = await EvaluationQualityGateService(comparisons).evaluate(
            knowledge_base_id=kb_id,
            dataset_id=dataset.id,
            first_run_id=first.id,
            second_run_id=second.id,
            thresholds=EvaluationQualityGateThresholds(max_mrr_drop=0.0),
        )
        assert gate.status is EvaluationQualityGateStatus.PASS


def test_chunk_replace_failure_rolls_back_and_embedding_upsert_is_atomic(
    postgres_url: str, tmp_path: Path
) -> None:
    asyncio.run(_chunk_transaction_round_trip(postgres_url, tmp_path))


async def _chunk_transaction_round_trip(postgres_url: str, tmp_path: Path) -> None:
    async with _isolated_database(postgres_url) as database:
        kb_id = await database.new_knowledge_base("Transactional integration")
        storage = LocalDocumentBlobStorage(tmp_path / "transactions")
        document_id = await _upload(
            database, storage, kb_id, "Refunds are processed in thirty days."
        )
        await _processor(database, storage, _DeterministicEmbeddings()).process(
            knowledge_base_id=kb_id, document_id=document_id
        )
        chunk_repository = SqlAlchemyDocumentChunkRepository(database.sessions)
        before = await chunk_repository.list_stored_by_document(
            document_id=document_id, limit=10, offset=0
        )
        assert len(before) == 1
        original_chunk_id = before[0].id

        # Bypass application-level validation to exercise real DB constraint rollback.
        with pytest.raises(DocumentChunkPersistenceError):
            await chunk_repository.replace_for_document(
                document_id=document_id,
                chunks=(
                    DocumentChunk(index=0, text="one", start_offset=0, end_offset=3),
                    DocumentChunk(index=0, text="two", start_offset=4, end_offset=7),
                ),
            )
        after = await chunk_repository.list_stored_by_document(
            document_id=document_id, limit=10, offset=0
        )
        assert [chunk.id for chunk in after] == [original_chunk_id]

        embedding_repository = SqlAlchemyChunkEmbeddingRepository(database.sessions)
        original = await embedding_repository.list_by_chunk(
            chunk_id=original_chunk_id, limit=10, offset=0
        )
        assert len(original) == 1
        assert original[0].vector.values == (1.0, 0.0, 0.0)

        replacement = ChunkEmbedding.create(
            chunk_id=original_chunk_id,
            provider="integration",
            model="fixture-3d",
            vector=EmbeddingVector.create([0.0, 1.0, 0.0], expected_dimensions=3),
        )
        await ChunkEmbeddingService(embedding_repository).upsert_batch((replacement,))
        updated = await embedding_repository.list_by_chunk(
            chunk_id=original_chunk_id, limit=10, offset=0
        )
        assert len(updated) == 1
        assert updated[0].vector.values == (0.0, 1.0, 0.0)

        assert (
            await SqlAlchemyDocumentRepository(database.sessions).get_by_id(
                knowledge_base_id=uuid4(), document_id=document_id
            )
            is None
        )


def test_reprocessing_preserves_identity_and_immutable_chunk_history(
    postgres_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Identical reprocessing is idempotent; changed chunking retains old evidence."""
    monkeypatch.setenv("SPUREL_API_TOKEN", _TEST_TOKEN)
    asyncio.run(_version_round_trip(postgres_url, tmp_path))


async def _version_round_trip(postgres_url: str, tmp_path: Path) -> None:
    async with _isolated_database(postgres_url) as database:
        kb_id = await database.new_knowledge_base("Versioned evidence")
        other_kb_id = await database.new_knowledge_base("Unrelated KB")
        storage = LocalDocumentBlobStorage(tmp_path / "versioned")
        provider = _DeterministicEmbeddings()
        doc_id = await _upload(
            database,
            storage,
            kb_id,
            "Refund requests are accepted within thirty days. "
            "Backup procedures are performed each morning. "
            "Additional refund requests require an approval.",
        )
        processor = _processor(database, storage, provider)
        chunks_repo = SqlAlchemyDocumentChunkRepository(database.sessions)
        version_repo = SqlAlchemyDocumentVersionRepository(database.sessions)
        versions = DocumentVersionService(version_repo)

        await processor.process(knowledge_base_id=kb_id, document_id=doc_id)
        first = await chunks_repo.list_stored_by_document(document_id=doc_id, limit=50, offset=0)
        assert len(first) == 1
        original_id = first[0].id
        document = await SqlAlchemyDocumentRepository(database.sessions).get_by_id(
            knowledge_base_id=kb_id, document_id=doc_id
        )
        assert document is not None
        assert document.active_chunk_version == 1

        # Existing relevance judgments point at real original chunk identities.
        evaluations = EvaluationDatasetService(
            SqlAlchemyEvaluationDatasetRepository(database.sessions)
        )
        dataset = await evaluations.create_dataset(knowledge_base_id=kb_id, name="Versioned labels")
        labeled = await evaluations.add_case(
            knowledge_base_id=kb_id,
            dataset_id=dataset.id,
            query="refund",
            judgments=(RelevanceJudgment(chunk_id=original_id, relevance=3),),
        )

        judgment_repository = SqlAlchemyEvaluationDatasetRepository(database.sessions)
        runs = EvaluationRunService(SqlAlchemyEvaluationRunRepository(database.sessions))
        benchmark = PersistedDatasetEvaluationService(
            executor=DatasetEvaluationExecutionService(
                repository=judgment_repository,
                retriever=KeywordDatasetRetriever(
                    KeywordRetrievalService(SqlAlchemyKeywordRetrievalRepository(database.sessions))
                ),
                mode=DatasetEvaluationMode.KEYWORD,
            ),
            runs=runs,
        )
        original_run = await benchmark.run(knowledge_base_id=kb_id, dataset_id=dataset.id, top_k=1)
        initial_audit = await evaluations.audit_judgments(
            knowledge_base_id=kb_id, dataset_id=dataset.id
        )
        assert initial_audit.is_usable
        assert initial_audit.invalid_count == 0

        # Processing the same data and chunk boundaries must not replace IDs.
        await processor.process(knowledge_base_id=kb_id, document_id=doc_id)
        same = await chunks_repo.list_stored_by_document(document_id=doc_id, limit=50, offset=0)
        assert [row.id for row in same] == [original_id]
        assert (
            len(
                await versions.list_versions(
                    knowledge_base_id=kb_id, document_id=doc_id, limit=50, offset=0
                )
            )
            == 1
        )

        # A new chunking strategy creates a new version without deleting old IDs.
        changed_processor = _processor(database, storage, provider, chunk_size=48)
        await changed_processor.process(knowledge_base_id=kb_id, document_id=doc_id)
        new_chunks = await chunks_repo.list_stored_by_document(
            document_id=doc_id, limit=50, offset=0
        )
        assert len(new_chunks) > 1
        assert original_id not in {row.id for row in new_chunks}

        current = await SqlAlchemyDocumentRepository(database.sessions).get_by_id(
            knowledge_base_id=kb_id, document_id=doc_id
        )
        assert current is not None and current.active_chunk_version == 2

        audit = await evaluations.audit_judgments(knowledge_base_id=kb_id, dataset_id=dataset.id)
        assert not audit.is_usable
        assert audit.invalid_count == 1
        assert audit.inactive_version_count == 1
        assert audit.issues[0].reason is EvaluationJudgmentIssueReason.INACTIVE_VERSION
        assert audit.issues[0].chunk_id == original_id
        assert audit.issues[0].document_id == doc_id
        assert audit.issues[0].chunk_version == 1
        assert audit.issues[0].active_chunk_version == 2

        with pytest.raises(EvaluationJudgmentStaleError):
            await benchmark.run(knowledge_base_id=kb_id, dataset_id=dataset.id, top_k=1)
        historical_runs = await runs.list_by_dataset(
            knowledge_base_id=kb_id, dataset_id=dataset.id, limit=10
        )
        assert [run.id for run in historical_runs] == [original_run.id]
        historical_run = await runs.get_by_id(
            knowledge_base_id=kb_id, dataset_id=dataset.id, run_id=original_run.id
        )
        assert historical_run.case_count == 1
        assert historical_run.mean_recall_at_k == 1.0

        history = await versions.list_versions(
            knowledge_base_id=kb_id, document_id=doc_id, limit=50, offset=0
        )
        assert [(row.version, row.is_active) for row in history] == [
            (2, True),
            (1, False),
        ]
        old_chunks = await versions.list_version_chunks(
            knowledge_base_id=kb_id,
            document_id=doc_id,
            version=1,
            limit=50,
            offset=0,
        )
        assert old_chunks[0].id == original_id
        assert old_chunks[0].embedding_count == 1
        assert (
            await evaluations.get_case(
                knowledge_base_id=kb_id, dataset_id=dataset.id, case_id=labeled.id
            )
        ).judgments[0].chunk_id == original_id

        vectors, keywords, hybrid, _ = _retrievers(database, provider)
        for matches in (
            await vectors.search(knowledge_base_id=kb_id, query="refund", limit=50),
            await keywords.search(knowledge_base_id=kb_id, query="refund", limit=50),
            await hybrid.search(
                knowledge_base_id=kb_id,
                query="refund",
                limit=10,
                candidate_limit=50,
            ),
        ):
            assert matches
            assert original_id not in {item.chunk_id for item in matches}
            assert {item.chunk_id for item in matches} <= {item.id for item in new_chunks}

        # Public history is explicitly read-only and cannot cross KBs.
        app = create_app()
        app.dependency_overrides[get_document_version_service] = lambda: versions
        app.dependency_overrides[get_evaluation_dataset_service] = lambda: evaluations
        app.dependency_overrides[get_keyword_dataset_evaluation_service] = lambda: benchmark
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = f"/knowledge-bases/{kb_id}/documents/{doc_id}"
            response = await client.get(f"{base}/versions", headers=headers)
            assert response.status_code == 200
            assert [item["version"] for item in response.json()["items"]] == [2, 1]
            result = await client.get(f"{base}/versions/1/chunks", headers=headers)
            assert result.status_code == 200
            assert result.json()["items"][0]["id"] == str(original_id)

            evaluation_path = f"/knowledge-bases/{kb_id}/evaluation-datasets/{dataset.id}"
            report = await client.get(f"{evaluation_path}/judgment-audit", headers=headers)
            assert report.status_code == 200, report.text
            assert report.json()["invalid_count"] == 1
            assert report.json()["issues"][0]["chunk_id"] == str(original_id)

            blocked = await client.post(
                f"{evaluation_path}/evaluate/keyword",
                headers=headers,
                json={"top_k": 1},
            )
            assert blocked.status_code == 409, blocked.text
            assert "judgment audit" in blocked.json()["detail"]

            assert (
                await client.get(
                    f"/knowledge-bases/{other_kb_id}/documents/{doc_id}/versions",
                    headers=headers,
                )
            ).status_code == 404
            assert (
                await client.get(
                    f"/knowledge-bases/{other_kb_id}/documents/{doc_id}/versions/1/chunks",
                    headers=headers,
                )
            ).status_code == 404

        # Identical second-version reprocessing is idempotent too.
        await changed_processor.process(knowledge_base_id=kb_id, document_id=doc_id)
        again = await chunks_repo.list_stored_by_document(document_id=doc_id, limit=50, offset=0)
        assert [row.id for row in again] == [row.id for row in new_chunks]
        assert (
            len(
                await versions.list_versions(
                    knowledge_base_id=kb_id, document_id=doc_id, limit=50, offset=0
                )
            )
            == 2
        )

        # Concurrent identical writes are serialized by the parent document lock.
        concurrent_chunks = tuple(row.chunk for row in again)
        await asyncio.gather(
            chunks_repo.replace_for_document(document_id=doc_id, chunks=concurrent_chunks),
            chunks_repo.replace_for_document(document_id=doc_id, chunks=concurrent_chunks),
        )
        after_concurrent = await chunks_repo.list_stored_by_document(
            document_id=doc_id, limit=50, offset=0
        )
        assert [row.id for row in after_concurrent] == [row.id for row in again]
        assert (
            len(
                await versions.list_versions(
                    knowledge_base_id=kb_id, document_id=doc_id, limit=50, offset=0
                )
            )
            == 2
        )


class _FailAfterOneBatch(_DeterministicEmbeddings):
    """Simulate failure after one committed embedding batch."""

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        self.calls += 1
        if self.calls == 2:
            raise EmbeddingProviderError("simulated embedding provider failure")
        return await super().embed(texts)


class _AlwaysFailEmbeddings(_DeterministicEmbeddings):
    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        raise EmbeddingProviderError("provider is unavailable")


def test_failed_embeddings_do_not_publish_and_retry_preserves_staged_ids(
    postgres_url: str, tmp_path: Path
) -> None:
    asyncio.run(_failed_embeddings_and_retry(postgres_url, tmp_path))


async def _failed_embeddings_and_retry(postgres_url: str, tmp_path: Path) -> None:
    async with _isolated_database(postgres_url) as database:
        kb_id = await database.new_knowledge_base("Retryable document")
        storage = LocalDocumentBlobStorage(tmp_path / "failed-retries")
        provider = _DeterministicEmbeddings()
        document_id = await _upload(
            database,
            storage,
            kb_id,
            "Refunds are available within thirty days. "
            "Manager approval is mandatory for replacements. "
            "Backups are maintained twice per day. "
            "Refund requests always require confirmation.",
        )
        documents = SqlAlchemyDocumentRepository(database.sessions)
        chunks = SqlAlchemyDocumentChunkRepository(database.sessions)
        versions = DocumentVersionService(SqlAlchemyDocumentVersionRepository(database.sessions))
        await _processor(database, storage, provider).process(
            knowledge_base_id=kb_id, document_id=document_id
        )
        active = await chunks.list_stored_by_document(document_id=document_id, limit=50, offset=0)
        assert len(active) == 1
        old_id = active[0].id

        failing = _FailAfterOneBatch()
        with pytest.raises(EmbeddingProviderError, match="simulated"):
            await _processor(database, storage, failing, chunk_size=42, batch_size=1).process(
                knowledge_base_id=kb_id, document_id=document_id
            )
        assert failing.calls == 2
        latest_document = await documents.get_by_id(
            knowledge_base_id=kb_id, document_id=document_id
        )
        assert latest_document is not None
        assert latest_document.active_chunk_version == 1

        historical = await versions.list_versions(
            knowledge_base_id=kb_id, document_id=document_id, limit=10, offset=0
        )
        assert [(item.version, item.status, item.is_active) for item in historical] == [
            (2, "failed", False),
            (1, "ready", True),
        ]
        failed_chunks = await versions.list_version_chunks(
            knowledge_base_id=kb_id, document_id=document_id, version=2, limit=50, offset=0
        )
        failed_ids = {row.id for row in failed_chunks}
        assert len(failed_ids) > 1
        assert sum(row.embedding_count for row in failed_chunks) == 1

        vectors, keywords, hybrid, _ = _retrievers(database, provider)
        old_matches = await keywords.search(knowledge_base_id=kb_id, query="refund", limit=10)
        assert [match.chunk_id for match in old_matches] == [old_id]
        assert [
            row.id
            for row in await chunks.list_stored_by_document(
                document_id=document_id, limit=50, offset=0
            )
        ] == [old_id]

        retry = await _processor(
            database, storage, _DeterministicEmbeddings(), chunk_size=42, batch_size=1
        ).process(knowledge_base_id=kb_id, document_id=document_id)
        assert retry.chunk_version == 2
        assert retry.reused_active_version is False

        after = await documents.get_by_id(knowledge_base_id=kb_id, document_id=document_id)
        assert after is not None and after.active_chunk_version == 2
        active_chunks = await chunks.list_stored_by_document(
            document_id=document_id, limit=50, offset=0
        )
        assert {row.id for row in active_chunks} == failed_ids
        history = await versions.list_versions(
            knowledge_base_id=kb_id, document_id=document_id, limit=10, offset=0
        )
        assert history[0].status == "ready"
        assert history[0].attempt_count == 2
        assert history[0].is_active is True

        # Only newly published chunks are searchable; old identity remains in history.
        for results in (
            await vectors.search(knowledge_base_id=kb_id, query="refund", limit=50),
            await keywords.search(knowledge_base_id=kb_id, query="refund", limit=50),
            await hybrid.search(
                knowledge_base_id=kb_id, query="refund", limit=10, candidate_limit=50
            ),
        ):
            assert results
            assert old_id not in {row.chunk_id for row in results}
            assert {row.chunk_id for row in results} <= failed_ids

        assert (
            await versions.list_version_chunks(
                knowledge_base_id=kb_id, document_id=document_id, version=1, limit=50, offset=0
            )
        )[0].id == old_id


def test_staged_version_cannot_publish_without_all_embeddings_and_is_fenced(
    postgres_url: str, tmp_path: Path
) -> None:
    asyncio.run(_staging_fencing_and_expiration(postgres_url, tmp_path))


async def _staging_fencing_and_expiration(postgres_url: str, tmp_path: Path) -> None:
    async with _isolated_database(postgres_url) as database:
        kb_id = await database.new_knowledge_base("Fenced staging")
        storage = LocalDocumentBlobStorage(tmp_path / "fencing")
        provider = _DeterministicEmbeddings()
        content = (
            "Refunds are available within thirty days. "
            "A manager approves an exception if needed. "
            "Backups are maintained every afternoon."
        )
        document_id = await _upload(database, storage, kb_id, content)
        await _processor(database, storage, provider).process(
            knowledge_base_id=kb_id, document_id=document_id
        )
        repository = SqlAlchemyDocumentChunkRepository(database.sessions)
        version_chunks = FixedSizeDocumentChunker(chunk_size=40, overlap=0).chunk(text=content)
        staging = await repository.replace_for_document(
            document_id=document_id, chunks=version_chunks
        )
        assert staging.version == 2
        assert staging.attempt_id is not None
        assert staging.reused_active is False

        with pytest.raises(DocumentChunkVersionIncompleteError):
            await repository.promote_version(
                document_id=document_id,
                version=staging.version,
                attempt_id=staging.attempt_id,
                provider=provider.provider,
                model=provider.model,
                dimensions=provider.dimensions,
            )

        with pytest.raises(DocumentProcessingConflictError):
            await repository.replace_for_document(document_id=document_id, chunks=version_chunks)

        # Simulate a worker disappearing: recovery can reclaim after lease expiry.
        async with database.sessions() as session:
            async with session.begin():
                await session.execute(
                    update(DocumentChunkVersionRecord)
                    .where(
                        DocumentChunkVersionRecord.document_id == document_id,
                        DocumentChunkVersionRecord.version == 2,
                    )
                    .values(lease_expires_at=datetime.now(UTC) - timedelta(minutes=1))
                )
        retry = await repository.replace_for_document(
            document_id=document_id, chunks=version_chunks
        )
        assert retry.version == staging.version
        assert retry.attempt_id is not None
        assert retry.attempt_id != staging.attempt_id
        with pytest.raises(DocumentProcessingConflictError):
            await repository.promote_version(
                document_id=document_id,
                version=staging.version,
                attempt_id=staging.attempt_id,
                provider=provider.provider,
                model=provider.model,
                dimensions=provider.dimensions,
            )
        # A stale attempt may not mark a reclaimed attempt failed.
        await repository.fail_version(
            document_id=document_id,
            version=staging.version,
            attempt_id=staging.attempt_id,
        )

        published = await SqlAlchemyDocumentRepository(database.sessions).get_by_id(
            knowledge_base_id=kb_id, document_id=document_id
        )
        assert published is not None
        assert published.active_chunk_version == 1
        history = await DocumentVersionService(
            SqlAlchemyDocumentVersionRepository(database.sessions)
        ).list_versions(knowledge_base_id=kb_id, document_id=document_id, limit=10, offset=0)
        assert history[0].status == "processing"
        assert history[0].attempt_count == 2

        await DocumentEmbeddingPipeline(
            chunk_reader=repository,
            provider=provider,
            embedding_service=ChunkEmbeddingService(
                SqlAlchemyChunkEmbeddingRepository(database.sessions)
            ),
            batch_size=1,
        ).run(
            document_id=document_id,
            chunk_version=retry.version,
            before_batch=lambda: repository.renew_version(
                document_id=document_id,
                version=retry.version,
                attempt_id=retry.attempt_id,
            ),
        )
        await repository.promote_version(
            document_id=document_id,
            version=retry.version,
            attempt_id=retry.attempt_id,
            provider=provider.provider,
            model=provider.model,
            dimensions=provider.dimensions,
        )
        activated = await SqlAlchemyDocumentRepository(database.sessions).get_by_id(
            knowledge_base_id=kb_id, document_id=document_id
        )
        assert activated is not None and activated.active_chunk_version == 2


def test_failed_initial_index_is_invisible_until_successful_retry(
    postgres_url: str, tmp_path: Path
) -> None:
    asyncio.run(_initial_index_failure_and_retry(postgres_url, tmp_path))


async def _initial_index_failure_and_retry(postgres_url: str, tmp_path: Path) -> None:
    async with _isolated_database(postgres_url) as database:
        kb_id = await database.new_knowledge_base("First time indexing")
        storage = LocalDocumentBlobStorage(tmp_path / "initial")
        document_id = await _upload(database, storage, kb_id, "Refund policy for employees.")
        with pytest.raises(EmbeddingProviderError):
            await _processor(database, storage, _AlwaysFailEmbeddings()).process(
                knowledge_base_id=kb_id, document_id=document_id
            )

        documents = SqlAlchemyDocumentRepository(database.sessions)
        doc = await documents.get_by_id(knowledge_base_id=kb_id, document_id=document_id)
        assert doc is not None and doc.active_chunk_version == 0
        repository = SqlAlchemyDocumentChunkRepository(database.sessions)
        assert not await repository.list_stored_by_document(
            document_id=document_id, limit=10, offset=0
        )
        assert not await SqlAlchemyKeywordRetrievalRepository(database.sessions).search(
            knowledge_base_id=kb_id, query="refund", limit=10
        )

        versions = DocumentVersionService(SqlAlchemyDocumentVersionRepository(database.sessions))
        failed = await versions.list_versions(
            knowledge_base_id=kb_id, document_id=document_id, limit=10, offset=0
        )
        assert len(failed) == 1
        assert failed[0].version == 1
        assert failed[0].status == "failed"

        retry = await _processor(database, storage, _DeterministicEmbeddings()).process(
            knowledge_base_id=kb_id, document_id=document_id
        )
        assert retry.chunk_version == 1
        assert (
            await documents.get_by_id(knowledge_base_id=kb_id, document_id=document_id)
        ).active_chunk_version == 1
        assert (
            await versions.list_versions(
                knowledge_base_id=kb_id, document_id=document_id, limit=10, offset=0
            )
        )[0].attempt_count == 2


def test_new_labels_reject_missing_foreign_and_deleted_chunk_references(
    postgres_url: str, tmp_path: Path
) -> None:
    """New labels must be active and scoped; old labels survive document deletion."""
    asyncio.run(_judgment_scope_and_missing_round_trip(postgres_url, tmp_path))


async def _judgment_scope_and_missing_round_trip(postgres_url: str, tmp_path: Path) -> None:
    async with _isolated_database(postgres_url) as database:
        own_kb = await database.new_knowledge_base("Judgment owner")
        foreign_kb = await database.new_knowledge_base("Foreign judgments")
        storage = LocalDocumentBlobStorage(tmp_path / "judgment-evidence")
        provider = _DeterministicEmbeddings()
        owned_document = await _upload(
            database, storage, own_kb, "Refund policy is available here."
        )
        foreign_document = await _upload(
            database, storage, foreign_kb, "Another refund policy exists."
        )
        for kb_id, document_id in (
            (own_kb, owned_document),
            (foreign_kb, foreign_document),
        ):
            await _processor(database, storage, provider).process(
                knowledge_base_id=kb_id, document_id=document_id
            )

        chunk_repo = SqlAlchemyDocumentChunkRepository(database.sessions)
        owned_chunk = (
            await chunk_repo.list_stored_by_document(document_id=owned_document, limit=10, offset=0)
        )[0].id
        foreign_chunk = (
            await chunk_repo.list_stored_by_document(
                document_id=foreign_document, limit=10, offset=0
            )
        )[0].id
        datasets = EvaluationDatasetService(
            SqlAlchemyEvaluationDatasetRepository(database.sessions)
        )
        dataset = await datasets.create_dataset(
            knowledge_base_id=own_kb, name="Current-only judgments"
        )

        for invalid_chunk_id in (uuid4(), foreign_chunk):
            with pytest.raises(EvaluationJudgmentInvalidError):
                await datasets.add_case(
                    knowledge_base_id=own_kb,
                    dataset_id=dataset.id,
                    query="refund",
                    judgments=(RelevanceJudgment(chunk_id=invalid_chunk_id, relevance=3),),
                )
        assert not await datasets.list_cases(knowledge_base_id=own_kb, dataset_id=dataset.id)

        case = await datasets.add_case(
            knowledge_base_id=own_kb,
            dataset_id=dataset.id,
            query="refund",
            judgments=(RelevanceJudgment(chunk_id=owned_chunk, relevance=3),),
        )
        before = await datasets.audit_judgments(knowledge_base_id=own_kb, dataset_id=dataset.id)
        assert before.is_usable and before.judgment_count == 1

        # A source may be deleted without cascading historical relevance labels.
        async with database.sessions() as session:
            async with session.begin():
                await session.execute(
                    delete(DocumentRecord).where(DocumentRecord.id == owned_document)
                )
        after = await datasets.audit_judgments(knowledge_base_id=own_kb, dataset_id=dataset.id)
        assert after.invalid_count == 1
        assert after.missing_or_out_of_scope_count == 1
        assert after.issues[0].reason is EvaluationJudgmentIssueReason.MISSING_OR_OUT_OF_SCOPE
        assert after.issues[0].document_id is None
        assert (
            await datasets.get_case(
                knowledge_base_id=own_kb, dataset_id=dataset.id, case_id=case.id
            )
        ).judgments[0].chunk_id == owned_chunk

        runs = EvaluationRunService(SqlAlchemyEvaluationRunRepository(database.sessions))
        runner = PersistedDatasetEvaluationService(
            executor=DatasetEvaluationExecutionService(
                repository=SqlAlchemyEvaluationDatasetRepository(database.sessions),
                retriever=KeywordDatasetRetriever(
                    KeywordRetrievalService(SqlAlchemyKeywordRetrievalRepository(database.sessions))
                ),
                mode=DatasetEvaluationMode.KEYWORD,
            ),
            runs=runs,
        )
        with pytest.raises(EvaluationJudgmentStaleError):
            await runner.run(knowledge_base_id=own_kb, dataset_id=dataset.id, top_k=1)
        assert not await runs.list_by_dataset(knowledge_base_id=own_kb, dataset_id=dataset.id)


def test_pdf_page_provenance_is_persisted_without_overwriting_existing_index(
    postgres_url: str, tmp_path: Path
) -> None:
    """SP-18: new page annotations create safe versions; legacy rows remain intact."""
    asyncio.run(_pdf_page_provenance_round_trip(postgres_url, tmp_path))


async def _pdf_page_provenance_round_trip(postgres_url: str, tmp_path: Path) -> None:
    async with _isolated_database(postgres_url) as database:
        kb_id = await database.new_knowledge_base("PDF provenance test")
        storage = LocalDocumentBlobStorage(tmp_path / "pdf-metadata")
        provider = _DeterministicEmbeddings()
        document_id = await _upload(database, storage, kb_id, "First policy page text.")
        await _processor(database, storage, provider).process(
            knowledge_base_id=kb_id, document_id=document_id
        )

        chunks = SqlAlchemyDocumentChunkRepository(database.sessions)
        original = await chunks.list_stored_by_document(document_id=document_id, limit=10, offset=0)
        assert len(original) == 1
        assert original[0].chunk.page_start is None
        legacy_id = original[0].id

        annotated = DocumentChunk(
            index=0,
            text=original[0].chunk.text,
            start_offset=original[0].chunk.start_offset,
            end_offset=original[0].chunk.end_offset,
            page_start=2,
            page_end=3,
            ocr_used=True,
        )
        staged = await chunks.replace_for_document(document_id=document_id, chunks=(annotated,))
        assert staged.version == 2
        assert staged.attempt_id is not None
        assert not staged.reused_active

        pending = await chunks.list_stored_by_document(
            document_id=document_id, limit=10, offset=0, chunk_version=2
        )
        assert pending[0].chunk == annotated

        embedded = await DocumentEmbeddingPipeline(
            chunk_reader=chunks,
            provider=provider,
            embedding_service=ChunkEmbeddingService(
                SqlAlchemyChunkEmbeddingRepository(database.sessions)
            ),
        ).run(document_id=document_id, chunk_version=2)
        await chunks.promote_version(
            document_id=document_id,
            version=2,
            attempt_id=staged.attempt_id,
            provider=embedded.provider,
            model=embedded.model,
            dimensions=embedded.dimensions,
        )

        current = await chunks.list_stored_by_document(document_id=document_id, limit=10, offset=0)
        assert len(current) == 1
        assert current[0].id != legacy_id
        assert current[0].chunk == annotated

        reader = SqlAlchemyChunkInspectorRepository(database.sessions)
        inspector = await reader.list_by_document(
            knowledge_base_id=kb_id, document_id=document_id, limit=10, offset=0
        )
        assert len(inspector) == 1
        assert (inspector[0].page_start, inspector[0].page_end) == (2, 3)
        assert inspector[0].ocr_used is True
        assert inspector[0].embedding_count == 1

        history = SqlAlchemyDocumentVersionRepository(database.sessions)
        legacy = await history.list_version_chunks(
            knowledge_base_id=kb_id, document_id=document_id, version=1, limit=10, offset=0
        )
        assert legacy is not None and len(legacy) == 1
        assert legacy[0].id == legacy_id
        assert legacy[0].page_start is None
        assert legacy[0].ocr_used is False

        repeated = await chunks.replace_for_document(document_id=document_id, chunks=(annotated,))
        assert repeated.reused_active
        assert repeated.version == 2
        unchanged = await chunks.list_stored_by_document(
            document_id=document_id, limit=10, offset=0
        )
        assert unchanged[0].id == current[0].id


def test_hnsw_operator_build_and_benchmark_use_real_postgres_without_provider(
    postgres_url: str, tmp_path: Path
) -> None:
    """Compare real ANN/exact query plans; never create embeddings with OpenAI."""
    asyncio.run(_hnsw_round_trip(postgres_url, tmp_path))


async def _hnsw_round_trip(postgres_url: str, tmp_path: Path) -> None:
    options = HnswIndexOptions(dimensions=3)
    created = False
    try:
        async with _isolated_database(postgres_url) as database:
            kb = await database.new_knowledge_base("HNSW recall integration")
            storage = LocalDocumentBlobStorage(tmp_path / "hnsw")
            doc = await _upload(
                database,
                storage,
                kb,
                "Refund policy and backup procedures. " * 10,
            )
            await _processor(database, storage, _DeterministicEmbeddings(), chunk_size=48).process(
                knowledge_base_id=kb, document_id=doc
            )

            # The existing application adapter remains exact, even after an
            # experimental HNSW index is created in this test database.
            exact_repository = SqlAlchemyVectorRetrievalRepository(database.sessions)
            built = await build_index(postgres_url, options)
            created = built["created"]
            assert built["valid"]
            assert built["dimensions"] == 3
            assert built["size_bytes"] > 0
            exact_matches = await exact_repository.search(
                knowledge_base_id=kb,
                query_vector=EmbeddingVector.create([1.0, 0.0, 0.0], expected_dimensions=3),
                provider="integration",
                model="fixture-3d",
                dimensions=3,
                limit=2,
            )
            assert len(exact_matches) >= 1
            again = await build_index(postgres_url, options)
            assert again["created"] is False

            result = await benchmark_index(
                postgres_url,
                HnswBenchmarkOptions(
                    knowledge_base_id=kb,
                    provider="integration",
                    model="fixture-3d",
                    dimensions=3,
                    top_k=2,
                    samples=3,
                    ef_search=80,
                ),
            )
            assert result["planner_used_hnsw"] is True
            assert result["measured_queries"] >= 1
            assert 0.0 <= result["mean_recall_at_k"] <= 1.0
            assert result["exact_median_ms"] >= 0.0
            assert result["hnsw_median_ms"] >= 0.0
            assert result["index"] == options.index_name
    finally:
        if created:
            # Clean up only the index this test itself created in a *_test DB.
            from sqlalchemy import text as sql_text

            engine = create_async_engine(postgres_url)
            try:
                async with engine.connect() as connection:
                    await connection.execution_options(isolation_level="AUTOCOMMIT")
                    await connection.execute(
                        sql_text(f"DROP INDEX CONCURRENTLY IF EXISTS {options.index_name}")
                    )
            finally:
                await engine.dispose()
