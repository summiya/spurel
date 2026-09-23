"""Evaluation dataset application boundaries."""

from spurel.evaluation_datasets.domain import (
    MAX_EVALUATION_DATASET_NAME_LENGTH,
    MAX_EVALUATION_QUERY_LENGTH,
    EvaluationCase,
    EvaluationCaseSummary,
    EvaluationDataset,
    EvaluationDatasetSummary,
    EvaluationDatasetValidationError,
)
from spurel.evaluation_datasets.execution import (
    MAX_DATASET_EVALUATION_CASES,
    MAX_DATASET_EVALUATION_JUDGMENTS,
    MAX_DATASET_EVALUATION_TOP_K,
    DatasetEvaluationCaseResult,
    DatasetEvaluationExecutionService,
    DatasetEvaluationLimitError,
    DatasetEvaluationMode,
    DatasetEvaluationQueryError,
    DatasetEvaluationResult,
    HybridDatasetRetriever,
    KeywordDatasetRetriever,
    VectorDatasetRetriever,
)
from spurel.evaluation_datasets.ports import (
    EvaluationDatasetLoadLimitError,
    EvaluationDatasetPersistenceError,
    EvaluationDatasetRepository,
)
from spurel.evaluation_datasets.service import (
    MAX_EVALUATION_DATASET_PAGE_SIZE,
    EvaluationDatasetNotFoundError,
    EvaluationDatasetQueryError,
    EvaluationDatasetService,
)

__all__ = [
    "MAX_DATASET_EVALUATION_CASES",
    "MAX_DATASET_EVALUATION_JUDGMENTS",
    "MAX_DATASET_EVALUATION_TOP_K",
    "DatasetEvaluationCaseResult",
    "DatasetEvaluationExecutionService",
    "DatasetEvaluationLimitError",
    "DatasetEvaluationMode",
    "DatasetEvaluationQueryError",
    "DatasetEvaluationResult",
    "HybridDatasetRetriever",
    "KeywordDatasetRetriever",
    "VectorDatasetRetriever",
    "MAX_EVALUATION_DATASET_NAME_LENGTH",
    "MAX_EVALUATION_DATASET_PAGE_SIZE",
    "MAX_EVALUATION_QUERY_LENGTH",
    "EvaluationCase",
    "EvaluationCaseSummary",
    "EvaluationDataset",
    "EvaluationDatasetNotFoundError",
    "EvaluationDatasetLoadLimitError",
    "EvaluationDatasetPersistenceError",
    "EvaluationDatasetQueryError",
    "EvaluationDatasetRepository",
    "EvaluationDatasetService",
    "EvaluationDatasetSummary",
    "EvaluationDatasetValidationError",
]
