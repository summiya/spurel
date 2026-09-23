"""Retrieval application boundaries."""

from spurel.retrieval.domain import (
    MAX_VECTOR_RETRIEVAL_RESULTS,
    VectorRetrievalMatch,
    VectorRetrievalQueryError,
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
from spurel.retrieval.service import (
    VectorRetrievalProviderContractError,
    VectorRetrievalService,
)

__all__ = [
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
