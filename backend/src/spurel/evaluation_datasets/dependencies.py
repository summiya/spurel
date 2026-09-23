"""Dependency wiring for evaluation datasets."""

from spurel.db import async_session_factory
from spurel.evaluation_datasets.service import EvaluationDatasetService
from spurel.evaluation_datasets.sqlalchemy_repository import (
    SqlAlchemyEvaluationDatasetRepository,
)


def get_evaluation_dataset_service() -> EvaluationDatasetService:
    """Build reusable evaluation dataset services."""
    return EvaluationDatasetService(
        SqlAlchemyEvaluationDatasetRepository(async_session_factory)
    )
