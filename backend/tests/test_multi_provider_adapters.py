"""SP-25 remote and local adapters use strict boundaries; no live network calls."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from spurel.embeddings.domain import (
    EmbeddingDimensionError,
    EmbeddingProviderError,
    EmbeddingResultError,
)
from spurel.generation.domain import TextGenerationRequest, TextGenerationResultError
from spurel.generation.ports import TextGenerationProviderError
from spurel.infrastructure.embeddings.ollama import OllamaEmbeddingProvider
from spurel.infrastructure.embeddings.openai_compatible import OpenAICompatibleEmbeddingProvider
from spurel.infrastructure.generation.ollama import OllamaTextGenerationProvider
from spurel.infrastructure.generation.openai_compatible import (
    OpenAICompatibleTextGenerationProvider,
)


def _generation_request():
    return TextGenerationRequest(
        system_prompt="Use only cited evidence.",
        user_prompt="Explain the saved policy.",
    )


def test_ollama_embeddings_use_native_batch_contract_and_validate_dimensions() -> None:
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://localhost:11434"
        ) as client:
            provider = OllamaEmbeddingProvider(client=client, model="embed-local", dimensions=2)
            result = await provider.embed(["first", "second"])
            assert provider.provider == "ollama"
            assert provider.dimensions == 2
            assert [vector.values for vector in result.vectors] == [
                (0.1, 0.2),
                (0.3, 0.4),
            ]

    asyncio.run(check())
    assert received[0][0] == "http://localhost:11434/api/embed"
    assert received[0][1] == {
        "model": "embed-local", "input": ["first", "second"], "truncate": False
    }


@pytest.mark.parametrize(
    "payload,error",
    [
        ({"embeddings": [[0.1, 0.2]]}, EmbeddingResultError),
        ({"embeddings": [[0.1, 0.2, 0.3], [0.1, 0.2]]}, EmbeddingDimensionError),
        ({"embeddings": [["NaN", 0.2], [0.1, 0.2]]}, EmbeddingResultError),
        ({"data": []}, EmbeddingResultError),
    ],
)
def test_ollama_embedding_bad_output_is_rejected(payload, error):
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
            base_url="http://localhost:11434",
        ) as client:
            with pytest.raises(error):
                await OllamaEmbeddingProvider(client=client, model="local", dimensions=2).embed(
                    ["a", "b"]
                )

    asyncio.run(check())


def test_ollama_failure_hides_server_output_and_does_not_redirect() -> None:
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(503, json={"error": "sensitive credential"})
            ),
            base_url="http://localhost:11434",
            follow_redirects=False,
        ) as client:
            with pytest.raises(EmbeddingProviderError) as error:
                await OllamaEmbeddingProvider(client=client, model="local", dimensions=2).embed(
                    ["sample"]
                )
            assert "sensitive" not in str(error.value)

    asyncio.run(check())


def test_ollama_chat_is_nonstreaming_and_uses_configured_output_bound() -> None:
    received = []

    def handler(request: httpx.Request):
        received.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"message": {"content": "A grounded answer."}})

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://localhost:11434"
        ) as client:
            provider = OllamaTextGenerationProvider(
                client=client, model="chat-local", max_output_tokens=160
            )
            answer = await provider.generate(_generation_request())
            assert (answer.provider, answer.model, answer.text) == (
                "ollama", "chat-local", "A grounded answer."
            )

    asyncio.run(check())
    assert received[0][0] == "/api/chat"
    assert received[0][1] == {
        "model": "chat-local",
        "messages": [
            {"role": "system", "content": "Use only cited evidence."},
            {"role": "user", "content": "Explain the saved policy."},
        ],
        "stream": False,
        "options": {"num_predict": 160},
    }


@pytest.mark.parametrize("body", [{"message": {"content": ""}}, {"message": {}}, {"oops": 1}])
def test_ollama_chat_rejects_invalid_or_empty_text(body):
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)),
            base_url="http://localhost:11434",
        ) as client:
            with pytest.raises(TextGenerationResultError):
                await OllamaTextGenerationProvider(
                    client=client, model="chat-local", max_output_tokens=100
                ).generate(_generation_request())

    asyncio.run(check())


class CompatibleEmbeddingResource:
    def __init__(self, vectors):
        self.vectors = vectors
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=v)
                for index, v in enumerate(self.vectors)
            ]
        )


class CompatibleChatResource:
    def __init__(self, text):
        self.text = text
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.text))]
        )


def test_compatible_embedding_omits_optional_dimensions_request_but_checks_response():
    resource = CompatibleEmbeddingResource([[0.2, 0.4]])
    provider = OpenAICompatibleEmbeddingProvider(
        client=SimpleNamespace(embeddings=resource), model="hosted-embed", dimensions=2
    )
    batch = asyncio.run(provider.embed(["sample"]))
    assert batch.vectors[0].values == (0.2, 0.4)
    assert provider.provider == "openai_compatible"
    assert resource.last_kwargs == {
        "model": "hosted-embed", "input": ["sample"], "encoding_format": "float"
    }

    resource.vectors = [[0.2]]
    with pytest.raises(EmbeddingDimensionError):
        asyncio.run(provider.embed(["sample"]))


def test_compatible_generation_uses_chat_completions_not_responses_api():
    resource = CompatibleChatResource("  Answer from citations.  ")
    client = SimpleNamespace(chat=SimpleNamespace(completions=resource))
    provider = OpenAICompatibleTextGenerationProvider(
        client=client, model="hosted-chat", max_output_tokens=900
    )
    answer = asyncio.run(provider.generate(_generation_request()))
    assert (answer.provider, answer.text) == ("openai_compatible", "Answer from citations.")
    assert resource.last_kwargs == {
        "model": "hosted-chat",
        "messages": [
            {"role": "system", "content": "Use only cited evidence."},
            {"role": "user", "content": "Explain the saved policy."},
        ],
        "max_tokens": 900,
    }

    resource.text = None
    with pytest.raises(TextGenerationResultError):
        asyncio.run(provider.generate(_generation_request()))


def test_ollama_http_error_does_not_expose_provider_body():
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(403, text="sensitive internal server details")
            ),
            base_url="http://localhost:11434",
        ) as client:
            with pytest.raises(TextGenerationProviderError) as error:
                await OllamaTextGenerationProvider(
                    client=client, model="chat-local", max_output_tokens=100
                ).generate(_generation_request())
            assert "sensitive" not in str(error.value)

    asyncio.run(check())
