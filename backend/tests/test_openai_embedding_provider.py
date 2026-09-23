import asyncio
from dataclasses import dataclass

import pytest

from spurel.embeddings import (
    EmbeddingProviderError,
    EmbeddingResultError,
)
from spurel.infrastructure.embeddings import OpenAIEmbeddingProvider


@dataclass
class FakeEmbeddingItem:
    index: int
    embedding: list[float]


@dataclass
class FakeEmbeddingResponse:
    data: list[FakeEmbeddingItem]


class FakeEmbeddingsResource:
    def __init__(self) -> None:
        self.response = FakeEmbeddingResponse(data=[])
        self.error: Exception | None = None
        self.last_kwargs: dict[str, object] | None = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddingsResource()


def test_openai_provider_embeds_batch_and_restores_input_order() -> None:
    client = FakeOpenAIClient()
    client.embeddings.response = FakeEmbeddingResponse(
        data=[
            FakeEmbeddingItem(index=1, embedding=[0.3, 0.4]),
            FakeEmbeddingItem(index=0, embedding=[0.1, 0.2]),
        ]
    )
    provider = OpenAIEmbeddingProvider(
        client=client,  # type: ignore[arg-type]
        model="text-embedding-example",
        dimensions=2,
    )

    batch = asyncio.run(provider.embed(["first", "second"]))

    assert provider.provider == "openai"
    assert provider.model == "text-embedding-example"
    assert provider.dimensions == 2
    assert [vector.values for vector in batch.vectors] == [
        (0.1, 0.2),
        (0.3, 0.4),
    ]
    assert client.embeddings.last_kwargs == {
        "model": "text-embedding-example",
        "input": ["first", "second"],
        "dimensions": 2,
        "encoding_format": "float",
    }


def test_openai_provider_rejects_invalid_response_indexes() -> None:
    client = FakeOpenAIClient()
    client.embeddings.response = FakeEmbeddingResponse(
        data=[
            FakeEmbeddingItem(index=0, embedding=[0.1, 0.2]),
            FakeEmbeddingItem(index=2, embedding=[0.3, 0.4]),
        ]
    )
    provider = OpenAIEmbeddingProvider(
        client=client,  # type: ignore[arg-type]
        model="text-embedding-example",
        dimensions=2,
    )

    with pytest.raises(EmbeddingResultError):
        asyncio.run(provider.embed(["first", "second"]))


def test_openai_provider_hides_sdk_failure_details() -> None:
    client = FakeOpenAIClient()
    client.embeddings.error = RuntimeError("secret provider details")
    provider = OpenAIEmbeddingProvider(
        client=client,  # type: ignore[arg-type]
        model="text-embedding-example",
        dimensions=2,
    )

    with pytest.raises(EmbeddingProviderError) as exc_info:
        asyncio.run(provider.embed(["hello"]))

    assert "secret provider details" not in str(exc_info.value)


def test_openai_provider_rejects_blank_model() -> None:
    client = FakeOpenAIClient()

    with pytest.raises(EmbeddingResultError):
        OpenAIEmbeddingProvider(
            client=client,  # type: ignore[arg-type]
            model="   ",
            dimensions=2,
        )
