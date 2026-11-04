"""Opt-in cross-encoder reranking over a bounded, fused hybrid candidate pool.

A provider adapter scores (query, document text) pairs. No request, network
access or model loading happens unless reranking was explicitly requested.
"""

import math
import os
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from spurel.retrieval.hybrid import HybridRetrievalMatch

MAX_RERANK_DOCUMENT_CHARS = 4_000
MAX_RERANK_CANDIDATES = 100


class RerankerUnavailableError(RuntimeError):
    """A reranker is unavailable or violated the score contract."""


class CrossEncoderReranker(Protocol):
    """Interchangeable provider for pairwise query/document relevance scores."""

    @property
    def model(self) -> str: ...

    async def score(self, *, query: str, documents: Sequence[str]) -> Sequence[float]: ...


@dataclass(frozen=True, slots=True)
class HttpCrossEncoderReranker:
    """Adapter to an operator-configured cross-encoder scoring service.

    Contract: POST {"model": "...", "query": "...", "documents": ["..."]}
    -> {"scores": [finite floating point score per document, in input order]}.
    The URL and bearer token are server-side environment settings, never API
    request fields or public client settings.
    """

    url: str
    model: str
    token: str | None = None

    def __post_init__(self) -> None:
        parsed = urlsplit(self.url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or parsed.query
        ):
            raise RerankerUnavailableError("reranker URL configuration is invalid")
        if not self.model.strip() or len(self.model) > 255:
            raise RerankerUnavailableError("reranker model configuration is invalid")

    @classmethod
    def from_env(cls) -> "HttpCrossEncoderReranker":
        url = os.getenv("SPUREL_RERANKER_URL", "")
        model = os.getenv("SPUREL_RERANKER_MODEL", "")
        if not url or not model:
            raise RerankerUnavailableError("cross-encoder reranking is not configured")
        return cls(
            url=url,
            model=model,
            token=os.getenv("SPUREL_RERANKER_TOKEN") or None,
        )

    async def score(self, *, query: str, documents: Sequence[str]) -> Sequence[float]:
        if not documents:
            return ()
        if len(documents) > MAX_RERANK_CANDIDATES:
            raise RerankerUnavailableError("rerank candidate pool exceeds 100")
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(20.0),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = await client.post(
                    self.url,
                    json={"model": self.model, "query": query, "documents": list(documents)},
                    headers=headers,
                )
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RerankerUnavailableError("cross-encoder scoring failed") from exc
        if not isinstance(body, dict) or not isinstance(body.get("scores"), list):
            raise RerankerUnavailableError("cross-encoder returned an invalid score list")
        return body["scores"]


async def rerank_hybrid_matches(
    *,
    reranker: CrossEncoderReranker,
    query: str,
    candidates: Sequence[HybridRetrievalMatch],
    top_k: int,
) -> tuple[HybridRetrievalMatch, ...]:
    """Rerank the actual fused pool, keeping source ranks, RRF scores, UUIDs.

    Scores are not probabilities. Ties are stable in original RRF order.
    A bad provider response fails closed instead of silently falling back.
    """
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 100:
        raise RerankerUnavailableError("invalid rerank result limit")
    if len(candidates) > MAX_RERANK_CANDIDATES:
        raise RerankerUnavailableError("rerank candidate pool exceeds 100")
    if not candidates:
        return ()
    if len({candidate.chunk_id for candidate in candidates}) != len(candidates):
        raise RerankerUnavailableError("duplicate rerank candidate identity")
    documents = [candidate.text[:MAX_RERANK_DOCUMENT_CHARS] for candidate in candidates]
    try:
        scores = await reranker.score(query=query, documents=documents)
    except RerankerUnavailableError:
        raise
    except Exception as exc:
        raise RerankerUnavailableError("cross-encoder scoring failed") from exc
    if len(scores) != len(candidates) or any(
        isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score)
        for score in scores
    ):
        raise RerankerUnavailableError("cross-encoder returned invalid or incomplete scores")

    ranked = sorted(
        enumerate(candidates, start=1),
        key=lambda pair: (-float(scores[pair[0] - 1]), pair[0]),
    )
    return tuple(
        replace(
            candidate,
            candidate_rank=original_rank,
            rerank_score=float(scores[original_rank - 1]),
            rerank_rank=final_rank,
        )
        for final_rank, (original_rank, candidate) in enumerate(ranked[:top_k], start=1)
    )
