import pytest

from spurel.embeddings import (
    MAX_EMBEDDING_BATCH_SIZE,
    EmbeddingBatch,
    EmbeddingBatchSizeError,
    EmbeddingDimensionError,
    EmbeddingResultError,
    EmbeddingVector,
)
from spurel.embeddings.domain import validate_embedding_inputs


def test_embedding_vector_is_immutable_and_validated() -> None:
    vector = EmbeddingVector.create(
        [0.1, 0.2, 0.3],
        expected_dimensions=3,
    )

    assert vector.values == (0.1, 0.2, 0.3)


def test_embedding_vector_rejects_wrong_dimensions() -> None:
    with pytest.raises(EmbeddingDimensionError):
        EmbeddingVector.create(
            [0.1, 0.2],
            expected_dimensions=3,
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_embedding_vector_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(EmbeddingResultError):
        EmbeddingVector.create(
            [0.1, value],
            expected_dimensions=2,
        )


def test_embedding_batch_preserves_input_order_and_metadata() -> None:
    batch = EmbeddingBatch.create(
        vectors=[
            [0.1, 0.2],
            [0.3, 0.4],
        ],
        input_count=2,
        model="example-embedding-model",
        dimensions=2,
    )

    assert batch.model == "example-embedding-model"
    assert batch.dimensions == 2
    assert [vector.values for vector in batch.vectors] == [
        (0.1, 0.2),
        (0.3, 0.4),
    ]


def test_embedding_batch_rejects_wrong_result_count() -> None:
    with pytest.raises(EmbeddingResultError):
        EmbeddingBatch.create(
            vectors=[[0.1, 0.2]],
            input_count=2,
            model="example",
            dimensions=2,
        )


@pytest.mark.parametrize(
    "texts",
    [
        [],
        ["ok", ""],
        ["ok", "   "],
        ["x"] * (MAX_EMBEDDING_BATCH_SIZE + 1),
    ],
)
def test_embedding_inputs_are_bounded_and_non_empty(texts: list[str]) -> None:
    with pytest.raises((EmbeddingBatchSizeError, EmbeddingResultError)):
        validate_embedding_inputs(texts)


@pytest.mark.parametrize("dimensions", [0, -1, True, 20_000])
def test_embedding_dimensions_are_bounded(dimensions: int) -> None:
    with pytest.raises(EmbeddingDimensionError):
        EmbeddingVector.create(
            [0.1],
            expected_dimensions=dimensions,
        )
