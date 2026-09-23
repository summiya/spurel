"""Retrieval application boundaries."""

from spurel.retrieval.domain import (
    MAX_VECTOR_RETRIEVAL_RESULTS,
    VectorRetrievalMatch,
    VectorRetrievalQueryError,
)
from spurel.retrieval.ports import (
    VectorRetrievalRepository,
    VectorRetrievalRepositoryError,
)
from spurel.retrieval.service import (
    VectorRetrievalProviderContractError,
    VectorRetrievalService,
)

__all__ = [
    "MAX_VECTOR_RETRIEVAL_RESULTS",
    "VectorRetrievalMatch",
    "VectorRetrievalProviderContractError",
    "VectorRetrievalQueryError",
    "VectorRetrievalRepository",
    "VectorRetrievalRepositoryError",
    "VectorRetrievalService",
]
