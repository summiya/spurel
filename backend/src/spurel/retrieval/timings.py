"""Request-scoped, measured retrieval stages (SP-22).

A context-local collector scopes work to one traced retrieval. Hybrid source
searches execute concurrently and share the current request's collector.
Stage durations can overlap; never add them together to infer wall time.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from time import perf_counter

STAGE_NAMES = frozenset(
    {"query_embedding", "vector_search", "keyword_search", "rrf_fusion", "cross_encoder"}
)

_active_stages: ContextVar[dict[str, float] | None] = ContextVar(
    "spurel_retrieval_stages", default=None
)


@contextmanager
def capture_stage_timings() -> Iterator[dict[str, float]]:
    """Keep one request's stage measurements isolated from concurrent requests."""
    stages: dict[str, float] = {}
    token: Token[dict[str, float] | None] = _active_stages.set(stages)
    try:
        yield stages
    finally:
        _active_stages.reset(token)


@contextmanager
def time_stage(stage: str) -> Iterator[None]:
    """Record observed elapsed milliseconds, only inside a traced request."""
    stages = _active_stages.get()
    if stages is None:
        yield
        return
    if stage not in STAGE_NAMES:
        raise ValueError("unknown retrieval timing stage")
    started = perf_counter()
    try:
        yield
    finally:
        stages[stage] = max(0.0, (perf_counter() - started) * 1_000.0)
