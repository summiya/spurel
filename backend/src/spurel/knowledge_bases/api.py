"""FastAPI endpoints for knowledge bases."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from spurel.knowledge_bases.dependencies import get_knowledge_base_service
from spurel.knowledge_bases.domain import KnowledgeBase, KnowledgeBaseNameError
from spurel.knowledge_bases.ports import KnowledgeBasePersistenceError
from spurel.knowledge_bases.schemas import (
    CreateKnowledgeBaseRequest,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
)
from spurel.knowledge_bases.service import KnowledgeBaseService

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

KnowledgeBaseServiceDependency = Annotated[
    KnowledgeBaseService,
    Depends(get_knowledge_base_service),
]


def _to_response(knowledge_base: KnowledgeBase) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=knowledge_base.id,
        name=knowledge_base.name,
        created_at=knowledge_base.created_at,
    )


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    payload: CreateKnowledgeBaseRequest,
    service: KnowledgeBaseServiceDependency,
) -> KnowledgeBaseResponse:
    """Create one knowledge base."""
    try:
        knowledge_base = await service.create(payload.name)
    except KnowledgeBaseNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="knowledge base name must not be blank",
        ) from exc
    except KnowledgeBasePersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="knowledge base service temporarily unavailable",
        ) from exc

    return _to_response(knowledge_base)


@router.get("", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    service: KnowledgeBaseServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> KnowledgeBaseListResponse:
    """List a bounded page of knowledge bases."""
    try:
        knowledge_bases = await service.list(limit=limit, offset=offset)
    except KnowledgeBasePersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="knowledge base service temporarily unavailable",
        ) from exc

    return KnowledgeBaseListResponse(
        items=[_to_response(item) for item in knowledge_bases],
        limit=limit,
        offset=offset,
    )
