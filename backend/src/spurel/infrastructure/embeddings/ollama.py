"""Native Ollama /api/embed adapter; no model downloads or implicit calls."""

from collections.abc import Sequence

import httpx

from spurel.embeddings.domain import (
    EmbeddingBatch,
    EmbeddingProviderError,
    EmbeddingResultError,
    validate_embedding_dimensions,
    validate_embedding_inputs,
)


class OllamaEmbeddingProvider:
    """Embed an ordered bounded batch using a trusted local Ollama server."""

    def __init__(self, *, client: httpx.AsyncClient, model: str, dimensions: int) -> None:
        if not model.strip():
            raise EmbeddingResultError("Ollama embedding model is missing")
        validate_embedding_dimensions(dimensions)
        self._client = client
        self._model = model.strip()
        self._dimensions = dimensions

    @property
    def provider(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        normalized = validate_embedding_inputs(texts)
        try:
            response = await self._client.post(
                "/api/embed",
                json={
                    "model": self._model,
                    "input": list(normalized),
                    "truncate": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EmbeddingProviderError("Ollama embedding request failed") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("embeddings"), list):
            raise EmbeddingResultError("Ollama embeddings response is invalid")
        vectors = payload["embeddings"]
        if not all(
            isinstance(vector, list)
            and all(
                isinstance(number, (int, float)) and not isinstance(number, bool)
                for number in vector
            )
            for vector in vectors
        ):
            raise EmbeddingResultError("Ollama embeddings contain invalid values")
        return EmbeddingBatch.create(
            vectors=vectors,
            input_count=len(normalized),
            model=self._model,
            dimensions=self._dimensions,
        )
