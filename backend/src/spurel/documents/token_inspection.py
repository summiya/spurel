"""Read-only exact token measurements for persisted source excerpts.

These counts are computed for the *currently configured* embedding model.
The model name/encoding is returned with the count, so old immutable chunk
versions are not mistaken for their original processing-tokenizer provenance.
"""

import os
from functools import lru_cache

from spurel.documents.chunking import DocumentChunkingConfigError
from spurel.infrastructure.chunking.token_aware import tokenizer_for_model


@lru_cache(maxsize=16)
def _encoding_name(model: str) -> str | None:
    try:
        return tokenizer_for_model(model).name
    except DocumentChunkingConfigError:
        return None


def measured_tokens(text: str) -> tuple[int | None, str | None]:
    """Return an exact tokenizer-specific count, or unavailable without guessing."""
    model = os.getenv("SPUREL_EMBEDDING_MODEL", "").strip()
    if not model:
        return (None, None)
    name = _encoding_name(model)
    if name is None:
        return (None, None)
    encoding = tokenizer_for_model(model)
    return (len(encoding.encode(text, disallowed_special=())), name)
