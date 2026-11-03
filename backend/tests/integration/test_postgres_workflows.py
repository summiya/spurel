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
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from spurel.documents.chunk_inspector import ChunkInspectorService
from spurel.documents.chunk_pipeline import DocumentChunkPipeline
from spurel.documents.chunk_ports import DocumentChunkPersistenceError
from spurel.documents.chunk_service import DocumentChunkService
from spurel.documents.chunking import DocumentChunk
from spurel.documents.dependencies import get_chunk_inspector_service, get_document_upload_service
from spurel.documents.domain import DocumentMediaType
from spurel.documents.ingestion_service import DocumentIngestionService
from spurel.documents.processing import DocumentProcessingService
from spurel.documents.processing_dependencies import get_document_processing_service
from spurel.documents.sqlalchemy_chunk_inspector_repository import (
    SqlAlchemyChunkInspectorRepository,
)
from spurel.documents.sqlalchemy_chunk_repository import SqlAlchemyDocumentChunkRepository
from spurel.documents.sqlalchemy_repository import SqlAlchemyDocumentRepository
from spurel.documents.storage import document_object_key
from spurel.documents.upload_service import DocumentUploadService
from spurel.embeddings.chunk import ChunkEmbedding
from spurel.embeddings.domain import EmbeddingBatch, EmbeddingVector
from spurel.embeddings.pipeline import DocumentEmbeddingPipeline
from spurel.embeddings.service import ChunkEmbeddingService
from spurel.embeddings.sqlalchemy_repository import SqlAlchemyChunkEmbeddingRepository
from spurel.evaluation_datasets.baseline_domain import EvaluationBaselineConfiguration
from spurel.evaluation_datasets.baseline_service import EvaluationBaselineService
from spurel.evaluation_datasets.execution import (
    DatasetEvaluationExecutionService,
    DatasetEvaluationMode,
    KeywordDatasetRetriever,
)
from spurel.evaluation_datasets.quality_gate import (
    EvaluationQualityGateService,
    EvaluationQualityGateStatus,
    EvaluationQualityGateThresholds,
)
from spurel.evaluation_datasets.run_comparison import EvaluationRunComparisonService
from spurel.evaluation_datasets.run_service import EvaluationRunService, PersistedDatasetEvaluationService
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
        chunker=FixedSizeDocumentChunker(chunk_size=512, overlap=0),
        chunk_service=DocumentChunkService(chunks),
    )
    return DocumentProcessingService(
        chunk_pipeline=chunk_pipeline,
        embedding_pipeline=DocumentEmbeddingPipeline(
            chunk_reader=chunks,
            provider=provider,
            embedding_service=ChunkEmbeddingService(embeddings),
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
                persisted = await traces.get_by_id(
                    knowledge_base_id=public_kb, trace_id=trace_id
                )
                assert persisted.results[0].document_id == uploaded_ids[0]
                assert persisted.mode.value == mode

            assert await traces.list_by_knowledge_base(
                knowledge_base_id=public_kb, limit=20
            )
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
                    KeywordRetrievalService(
                        SqlAlchemyKeywordRetrievalRepository(database.sessions)
                    )
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

        assert await SqlAlchemyDocumentRepository(database.sessions).get_by_id(
            knowledge_base_id=uuid4(), document_id=document_id
        ) is None
