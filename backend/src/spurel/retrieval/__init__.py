"""Retrieval application boundaries."""

from spurel.retrieval.domain import (
    MAX_VECTOR_RETRIEVAL_RESULTS,
    VectorRetrievalMatch,
    VectorRetrievalQueryError,
)
from spurel.retrieval.hybrid import (
    DEFAULT_HYBRID_CANDIDATE_LIMIT,
    DEFAULT_RRF_K,
    MAX_HYBRID_RETRIEVAL_RESULTS,
    HybridRetrievalMatch,
    HybridRetrievalQueryError,
    HybridRetrievalResultError,
    HybridRetrievalService,
)
from spurel.retrieval.keyword_domain import (
    MAX_KEYWORD_RETRIEVAL_RESULTS,
    KeywordRetrievalMatch,
    KeywordRetrievalQueryError,
)
from spurel.retrieval.keyword_ports import (
    KeywordRetrievalRepository,
    KeywordRetrievalRepositoryError,
)
from spurel.retrieval.keyword_service import KeywordRetrievalService
from spurel.retrieval.ports import (
    VectorRetrievalRepository,
    VectorRetrievalRepositoryError,
)
from spurel.retrieval.trace_comparison import (
    RetrievalTraceComparison,
    RetrievalTraceComparisonIntegrityError,
    RetrievalTraceComparisonQueryError,
    RetrievalTraceComparisonResult,
    RetrievalTraceComparisonService,
    RetrievalTraceComparisonSide,
)
from spurel.retrieval.trace_ports import (
    RetrievalTracePersistenceError,
    RetrievalTraceRepository,
)
from spurel.retrieval.trace_service import (
    MAX_RETRIEVAL_TRACE_PAGE_SIZE,
    RetrievalTraceNotFoundError,
    RetrievalTraceQueryError,
    RetrievalTraceService,
)
from spurel.retrieval.traced import (
    TracedHybridRetrievalService,
    TracedKeywordRetrievalService,
    TracedRetrievalResult,
    TracedVectorRetrievalService,
)
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceResult,
    RetrievalTraceSummary,
    RetrievalTraceValidationError,
)
from spurel.retrieval.service import (
    VectorRetrievalProviderContractError,
    VectorRetrievalService,
)

__all__ = [
    "RetrievalTraceComparison",
    "RetrievalTraceComparisonIntegrityError",
    "RetrievalTraceComparisonQueryError",
    "RetrievalTraceComparisonResult",
    "RetrievalTraceComparisonService",
    "RetrievalTraceComparisonSide",
    "MAX_RETRIEVAL_TRACE_PAGE_SIZE",
    "RetrievalTraceNotFoundError",
    "RetrievalTraceQueryError",
    "RetrievalTraceSummary",
    "TracedHybridRetrievalService",
    "TracedKeywordRetrievalService",
    "TracedRetrievalResult",
    "TracedVectorRetrievalService",
    "RetrievalTrace",
    "RetrievalTraceMode",
    "RetrievalTracePersistenceError",
    "RetrievalTraceRepository",
    "RetrievalTraceResult",
    "RetrievalTraceService",
    "RetrievalTraceValidationError",
    "DEFAULT_HYBRID_CANDIDATE_LIMIT",
    "DEFAULT_RRF_K",
    "MAX_HYBRID_RETRIEVAL_RESULTS",
    "HybridRetrievalMatch",
    "HybridRetrievalQueryError",
    "HybridRetrievalResultError",
    "HybridRetrievalService",
    "MAX_KEYWORD_RETRIEVAL_RESULTS",
    "KeywordRetrievalMatch",
    "KeywordRetrievalQueryError",
    "KeywordRetrievalRepository",
    "KeywordRetrievalRepositoryError",
    "KeywordRetrievalService",
    "MAX_VECTOR_RETRIEVAL_RESULTS",
    "VectorRetrievalMatch",
    "VectorRetrievalProviderContractError",
    "VectorRetrievalQueryError",
    "VectorRetrievalRepository",
    "VectorRetrievalRepositoryError",
    "VectorRetrievalService",
]
