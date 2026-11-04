"""Explicit, dimension-specific pgvector HNSW management and measured recall.

SP-20 does not change live retrieval to approximate search. Operators can
concurrently build an index for one dimension and benchmark it against exact
PostgreSQL cosine ranking using saved active vectors, without provider calls.
"""

import json
import math
import statistics
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

MAX_HNSW_DIMENSIONS = 2000
MAX_BENCHMARK_QUERIES = 100
MAX_TOP_K = 100
MAX_EF_SEARCH = 1000


class HnswConfigurationError(ValueError):
    """Unsafe index or benchmarking configuration."""


class HnswBenchmarkError(RuntimeError):
    """The requested comparison cannot be measured reliably."""


@dataclass(frozen=True, slots=True)
class HnswIndexOptions:
    """Bounded HNSW settings for one dimensional embedding space."""

    dimensions: int
    m: int = 16
    ef_construction: int = 64

    def __post_init__(self) -> None:
        if not _bounded_int(self.dimensions, 1, MAX_HNSW_DIMENSIONS):
            raise HnswConfigurationError("HNSW vector dimensions must be 1–2000")
        if not _bounded_int(self.m, 4, 64):
            raise HnswConfigurationError("HNSW m must be 4–64")
        if not _bounded_int(self.ef_construction, self.m * 2, 512):
            raise HnswConfigurationError("HNSW ef_construction must be 2*m–512")

    @property
    def index_name(self) -> str:
        return f"ix_spurel_hnsw_cosine_d{self.dimensions}"

    @property
    def build_statement(self) -> str:
        """All interpolations are validated integers; no identifier is user supplied."""
        return (
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {self.index_name} "
            "ON chunk_embeddings USING hnsw "
            f"((embedding::vector({self.dimensions})) vector_cosine_ops) "
            f"WITH (m = {self.m}, ef_construction = {self.ef_construction}) "
            f"WHERE dimensions = {self.dimensions}"
        )


@dataclass(frozen=True, slots=True)
class HnswBenchmarkOptions:
    """Exact and ANN probes run over the same indexed, active KB scope."""

    knowledge_base_id: UUID
    provider: str
    model: str
    dimensions: int
    top_k: int = 10
    samples: int = 20
    ef_search: int = 100

    def __post_init__(self) -> None:
        if not isinstance(self.knowledge_base_id, UUID):
            raise HnswConfigurationError("a knowledge-base UUID is required")
        if not self.provider or not self.provider.strip() or len(self.provider) > 64:
            raise HnswConfigurationError("provider is invalid")
        if not self.model or not self.model.strip() or len(self.model) > 255:
            raise HnswConfigurationError("model is invalid")
        if not _bounded_int(self.dimensions, 1, MAX_HNSW_DIMENSIONS):
            raise HnswConfigurationError("HNSW vector dimensions must be 1–2000")
        if not _bounded_int(self.top_k, 1, MAX_TOP_K):
            raise HnswConfigurationError("top_k must be 1–100")
        if not _bounded_int(self.samples, 1, MAX_BENCHMARK_QUERIES):
            raise HnswConfigurationError("samples must be 1–100")
        if not _bounded_int(self.ef_search, self.top_k, MAX_EF_SEARCH):
            raise HnswConfigurationError("ef_search must be between top_k and 1000")

    @property
    def index_name(self) -> str:
        return HnswIndexOptions(dimensions=self.dimensions).index_name


def _bounded_int(value: object, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


async def index_state(engine: AsyncEngine, options: HnswIndexOptions) -> dict | None:
    """Inspect the actual database index, including incomplete concurrent builds."""
    statement = text(
        "SELECT ix.indisvalid, ix.indisready, "
        "pg_get_indexdef(ix.indexrelid) AS definition, "
        "pg_relation_size(ix.indexrelid) AS size_bytes "
        "FROM pg_index ix "
        "JOIN pg_class idx ON idx.oid = ix.indexrelid "
        "WHERE ix.indrelid = to_regclass('chunk_embeddings') "
        "AND idx.relname = :name"
    )
    async with engine.connect() as connection:
        result = await connection.execute(statement, {"name": options.index_name})
        row = result.mappings().first()
    if row is None:
        return None
    definition = str(row["definition"])
    # Detect mismatched/invalid indexes instead of trusting IF NOT EXISTS.
    if (
        "USING hnsw" not in definition
        or "vector_cosine_ops" not in definition
        or f"vector({options.dimensions})" not in definition
        or f"dimensions = {options.dimensions}" not in definition
        or not row["indisvalid"]
        or not row["indisready"]
    ):
        raise HnswBenchmarkError("existing HNSW index is invalid or has unexpected definition")
    return {
        "name": options.index_name,
        "dimensions": options.dimensions,
        "valid": True,
        "size_bytes": int(row["size_bytes"]),
    }


async def build_index(database_url: str, options: HnswIndexOptions) -> dict:
    """Build concurrently only when the operator explicitly invokes this command.

    No migration, reprocessing, embedding generation or automatic index removal.
    """
    engine = create_async_engine(database_url)
    try:
        present = await index_state(engine, options)
        if present is not None:
            return {**present, "created": False}

        # CREATE INDEX CONCURRENTLY is forbidden inside a transaction.
        async with engine.connect() as connection:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.execute(text(options.build_statement))

        new_index = await index_state(engine, options)
        if new_index is None:
            raise HnswBenchmarkError("HNSW index build was not found afterward")
        return {**new_index, "created": True}
    finally:
        await engine.dispose()


def _retrieval_query(options: HnswBenchmarkOptions, *, exact: bool) -> str:
    """Keep the same scope and cosine distance; only the access path differs."""
    dimensions = options.dimensions
    distance = (
        f"ce.embedding::vector({dimensions}) "
        f"<=> CAST(:query_vector AS vector({dimensions}))"
    )
    order = f"({distance}) + 0" if exact else distance
    return (
        "SELECT ce.chunk_id FROM chunk_embeddings AS ce "
        "JOIN document_chunks AS dc ON dc.id = ce.chunk_id "
        "JOIN documents AS d ON d.id = dc.document_id "
        "WHERE d.knowledge_base_id = :knowledge_base_id "
        "AND dc.chunk_version = d.active_chunk_version "
        "AND ce.provider = :provider AND ce.model = :model "
        f"AND ce.dimensions = {dimensions} "
        f"ORDER BY {order} ASC"
        + (", ce.chunk_id ASC " if exact else " ")
        + "LIMIT :top_k"
    )


_SAMPLE_SQL = text(
    "SELECT ce.embedding::text AS embedding FROM chunk_embeddings AS ce "
    "JOIN document_chunks AS dc ON dc.id = ce.chunk_id "
    "JOIN documents AS d ON d.id = dc.document_id "
    "WHERE d.knowledge_base_id = :knowledge_base_id "
    "AND dc.chunk_version = d.active_chunk_version "
    "AND ce.provider = :provider AND ce.model = :model "
    "AND ce.dimensions = :dimensions "
    "ORDER BY ce.chunk_id ASC LIMIT :samples"
)


def _query_params(
    options: HnswBenchmarkOptions, query_vector: str
) -> dict[str, object]:
    return {
        "knowledge_base_id": options.knowledge_base_id,
        "provider": options.provider,
        "model": options.model,
        "query_vector": query_vector,
        "top_k": options.top_k,
    }


def _vector_literal(value: object, dimensions: int) -> str:
    """Serialize only already-persisted finite vectors, never raw SQL text."""
    try:
        decoded = json.loads(value) if isinstance(value, str) else value
        items = tuple(float(item) for item in decoded)
    except (TypeError, ValueError, OverflowError, json.JSONDecodeError) as exc:
        raise HnswBenchmarkError("stored query vector is invalid") from exc
    if len(items) != dimensions or not all(math.isfinite(v) for v in items):
        raise HnswBenchmarkError("stored vector dimensions or values are invalid")
    return json.dumps(items, separators=(",", ":"))


def _plan_uses_index(plan: object, index_name: str) -> bool:
    """Inspect structured EXPLAIN output instead of claiming ANN without proof."""
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except json.JSONDecodeError:
            return False
    if isinstance(plan, list):
        return any(_plan_uses_index(part, index_name) for part in plan)
    if isinstance(plan, dict):
        if plan.get("Index Name") == index_name:
            return True
        return any(_plan_uses_index(part, index_name) for part in plan.values())
    return False


async def _timed_search(
    sessions: async_sessionmaker[AsyncSession],
    options: HnswBenchmarkOptions,
    query_vector: str,
    *,
    exact: bool,
    verify_index: bool,
) -> tuple[tuple[UUID, ...], float]:
    """Use transaction-local planner flags and return *query-only* wall time."""
    sql = _retrieval_query(options, exact=exact)
    params = _query_params(options, query_vector)
    async with sessions() as session:
        async with session.begin():
            if exact:
                # The HNSW index cannot silently change the exact baseline.
                await session.execute(text("SET LOCAL enable_indexscan = off"))
                await session.execute(text("SET LOCAL enable_bitmapscan = off"))
            else:
                await session.execute(text("SET LOCAL enable_seqscan = off"))
                await session.execute(text("SET LOCAL enable_sort = off"))
                await session.execute(text(f"SET LOCAL hnsw.ef_search = {options.ef_search}"))
                await session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
                if verify_index:
                    explained = await session.execute(text("EXPLAIN (FORMAT JSON) " + sql), params)
                    if not _plan_uses_index(explained.scalar_one(), options.index_name):
                        raise HnswBenchmarkError(
                            "PostgreSQL did not plan an HNSW index scan; "
                            "cannot report an approximate-search benchmark"
                        )

            started = perf_counter()
            matches = await session.execute(text(sql), params)
            elapsed_ms = (perf_counter() - started) * 1000.0
            ids = tuple(row[0] for row in matches)
            return (ids, elapsed_ms)


def _percentile_95(values: list[float]) -> float:
    """Nearest-rank p95 is defined even for a single measured query."""
    return sorted(values)[math.ceil(0.95 * len(values)) - 1]


def _summarize(
    *,
    options: HnswBenchmarkOptions,
    size_bytes: int,
    recalls: list[float],
    exact_ms: list[float],
    hnsw_ms: list[float],
    sampled: int,
) -> dict:
    """Expose observed data only, including the sample and methodological caveats."""
    if not recalls or len(recalls) != len(exact_ms) or len(recalls) != len(hnsw_ms):
        raise HnswBenchmarkError("no comparable exact/HNSW measurements")
    return {
        "status": "measured",
        "index": options.index_name,
        "index_bytes": size_bytes,
        "knowledge_base_id": str(options.knowledge_base_id),
        "provider": options.provider,
        "model": options.model,
        "dimensions": options.dimensions,
        "top_k": options.top_k,
        "ef_search": options.ef_search,
        "requested_samples": options.samples,
        "measured_queries": len(recalls),
        "sampled_vectors": sampled,
        "mean_recall_at_k": statistics.fmean(recalls),
        "min_recall_at_k": min(recalls),
        "exact_median_ms": statistics.median(exact_ms),
        "hnsw_median_ms": statistics.median(hnsw_ms),
        "exact_p95_ms": _percentile_95(exact_ms),
        "hnsw_p95_ms": _percentile_95(hnsw_ms),
        "planner_used_hnsw": True,
        "limitations": (
            "Query vectors were sampled from stored active embeddings (self-query bias). "
            "Timing includes database execution and client transfer, not provider calls. "
            "Small or filtered sets may show worse latency or recall; no speedup is assumed."
        ),
    }


async def benchmark_index(database_url: str, options: HnswBenchmarkOptions) -> dict:
    """Measure real HNSW recall and query timings against exact scoped cosine search."""
    engine = create_async_engine(database_url)
    try:
        index = await index_state(engine, HnswIndexOptions(dimensions=options.dimensions))
        if index is None:
            raise HnswBenchmarkError(
                "no HNSW index exists for this dimension; run the explicit build command first"
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            result = await session.execute(
                _SAMPLE_SQL,
                {
                    "knowledge_base_id": options.knowledge_base_id,
                    "provider": options.provider,
                    "model": options.model,
                    "dimensions": options.dimensions,
                    "samples": options.samples,
                },
            )
            vectors = tuple(
                _vector_literal(row[0], options.dimensions) for row in result
            )
        if not vectors:
            raise HnswBenchmarkError(
                "no active stored vectors match the requested knowledge base and embedding space"
            )

        recalls: list[float] = []
        exact_ms: list[float] = []
        hnsw_ms: list[float] = []
        for vector in vectors:
            exact, duration_exact = await _timed_search(
                sessions, options, vector, exact=True, verify_index=False
            )
            approx, duration_hnsw = await _timed_search(
                sessions, options, vector, exact=False, verify_index=True
            )
            if not exact:
                raise HnswBenchmarkError("exact retrieval unexpectedly returned no results")
            recalls.append(len(set(exact) & set(approx)) / len(set(exact)))
            exact_ms.append(duration_exact)
            hnsw_ms.append(duration_hnsw)

        return _summarize(
            options=options,
            size_bytes=index["size_bytes"],
            recalls=recalls,
            exact_ms=exact_ms,
            hnsw_ms=hnsw_ms,
            sampled=len(vectors),
        )
    finally:
        await engine.dispose()
