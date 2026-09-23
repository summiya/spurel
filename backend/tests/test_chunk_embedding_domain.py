from uuid import uuid4

import pytest

from spurel.embeddings.chunk import ChunkEmbedding, ChunkEmbeddingMetadataError
from spurel.embeddings.domain import EmbeddingVector


def test_chunk_embedding_normalizes_provider_and_preserves_model() -> None:
    embedding = ChunkEmbedding.create(
        chunk_id=uuid4(),
        provider=" OpenAI ",
        model="text-embedding-3-small",
        vector=EmbeddingVector.create(
            [0.1, 0.2],
            expected_dimensions=2,
        ),
    )

    assert embedding.provider == "openai"
    assert embedding.model == "text-embedding-3-small"
    assert embedding.dimensions == 2


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("", "model"),
        ("   ", "model"),
        ("openai", ""),
        ("openai", "   "),
    ],
)
def test_chunk_embedding_rejects_blank_space_identity(
    provider: str,
    model: str,
) -> None:
    with pytest.raises(ChunkEmbeddingMetadataError):
        ChunkEmbedding.create(
            chunk_id=uuid4(),
            provider=provider,
            model=model,
            vector=EmbeddingVector.create(
                [0.1],
                expected_dimensions=1,
            ),
        )
