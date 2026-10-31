"""Tenant and document permission aware knowledge REST APIs."""

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.bootstrap.config import Settings
from nexus.modules.auth.dependencies import get_transaction
from nexus.modules.knowledge.domain import (
    AnswerProvider,
    DocumentVisibility,
    EmbeddingProvider,
    KnowledgeNotFoundError,
    KnowledgeValidationError,
)
from nexus.modules.knowledge.models import KnowledgeDocument
from nexus.modules.knowledge.schemas import (
    KnowledgeAnswerResponse,
    KnowledgeCitation,
    KnowledgeDocumentResponse,
    KnowledgeQuestionRequest,
)
from nexus.modules.knowledge.service import KnowledgeService
from nexus.modules.organizations.dependencies import TenantContextDependency
from nexus.modules.organizations.domain import Permission, has_permission
from nexus.platform.api.errors import ApplicationError

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]


def document_response(document: KnowledgeDocument) -> KnowledgeDocumentResponse:
    return KnowledgeDocumentResponse(
        id=document.id,
        filename=document.filename,
        media_type=document.media_type,
        file_size=document.file_size,
        visibility=cast(DocumentVisibility, document.visibility),
        status=cast(Literal["ready", "failed"], document.status),
        chunk_count=document.chunk_count,
        embedding_model=document.embedding_model,
        created_at=document.created_at,
    )


def denied() -> ApplicationError:
    return ApplicationError(
        code="tenant_access_denied",
        message="You do not have permission to perform this action.",
        status_code=status.HTTP_403_FORBIDDEN,
    )


def service(request: Request, session: AsyncSession) -> KnowledgeService:
    return KnowledgeService(
        session,
        cast(EmbeddingProvider, request.app.state.knowledge_embedding_provider),
        cast(AnswerProvider, request.app.state.knowledge_answer_provider),
    )


@router.post("/documents", response_model=KnowledgeDocumentResponse, status_code=201)
async def upload_document(
    request: Request,
    session: SessionDependency,
    context: TenantContextDependency,
    file: Annotated[UploadFile, File()],
    visibility: Annotated[DocumentVisibility, Form()] = "organization",
) -> KnowledgeDocumentResponse:
    if not has_permission(context.role, Permission.KNOWLEDGE_WRITE):
        raise denied()
    settings = cast(Settings, request.app.state.settings)
    content = await file.read(settings.knowledge_max_file_bytes + 1)
    await file.close()
    if not content:
        raise ApplicationError(
            code="empty_document", message="The document is empty.", status_code=422
        )
    if len(content) > settings.knowledge_max_file_bytes:
        raise ApplicationError(
            code="document_too_large",
            message="The document exceeds the configured size limit.",
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        )
    try:
        document = await service(request, session).ingest(
            organization_id=context.organization_id,
            user_id=context.user_id,
            filename=file.filename or "",
            media_type=file.content_type or "application/octet-stream",
            content=content,
            visibility=visibility,
        )
    except KnowledgeValidationError as exc:
        raise ApplicationError(
            code=str(exc), message="The document could not be processed.", status_code=422
        ) from exc
    return document_response(document)


@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
async def list_documents(
    request: Request, session: SessionDependency, context: TenantContextDependency
) -> list[KnowledgeDocumentResponse]:
    if not has_permission(context.role, Permission.KNOWLEDGE_READ):
        raise denied()
    documents = await service(request, session).list_documents(
        context.organization_id, context.user_id, context.role
    )
    return [document_response(document) for document in documents]


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    request: Request,
    session: SessionDependency,
    context: TenantContextDependency,
) -> None:
    if not has_permission(context.role, Permission.KNOWLEDGE_WRITE):
        raise denied()
    try:
        await service(request, session).delete_document(
            document_id, context.organization_id, context.user_id, context.role
        )
    except KnowledgeNotFoundError as exc:
        raise ApplicationError(
            code="knowledge_document_not_found",
            message="The document was not found.",
            status_code=404,
        ) from exc


@router.post("/answer", response_model=KnowledgeAnswerResponse)
async def answer_question(
    body: KnowledgeQuestionRequest,
    request: Request,
    session: SessionDependency,
    context: TenantContextDependency,
) -> KnowledgeAnswerResponse:
    if not has_permission(context.role, Permission.KNOWLEDGE_READ):
        raise denied()
    settings = cast(Settings, request.app.state.settings)
    answer, evidence, supported = await service(request, session).answer(
        organization_id=context.organization_id,
        user_id=context.user_id,
        role=context.role,
        question=body.question,
        limit=settings.knowledge_retrieval_limit,
        distance_threshold=settings.knowledge_distance_threshold,
    )
    return KnowledgeAnswerResponse(
        answer=answer,
        supported=supported,
        citations=[
            KnowledgeCitation(
                document_id=UUID(item.document_id),
                document_name=item.document_name,
                chunk_ordinal=item.chunk_ordinal,
                excerpt=item.content[:240],
                distance=item.distance,
            )
            for item in evidence
        ],
    )
