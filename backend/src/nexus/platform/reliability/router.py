"""Tenant-scoped reliability diagnostics and reconciliation APIs."""

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.dependencies import get_transaction
from nexus.modules.organizations.dependencies import TenantContextDependency
from nexus.modules.organizations.domain import Permission, has_permission
from nexus.platform.api.errors import ApplicationError
from nexus.platform.reliability.models import OutboxEvent
from nexus.platform.reliability.service import ReconciliationService

router = APIRouter(prefix="/reliability", tags=["reliability"])
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]


class OutboxEventResponse(BaseModel):
    id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    correlation_id: str | None
    status: Literal["pending", "processing", "published", "dead"]
    attempt_count: int
    max_attempts: int
    available_at: datetime
    created_at: datetime
    published_at: datetime | None


class ReconciliationFindingResponse(BaseModel):
    id: UUID
    finding_code: str
    aggregate_type: str
    aggregate_id: UUID
    status: Literal["open", "resolved"]
    details: dict[str, object]
    correlation_id: str | None
    detected_at: datetime


class ReconciliationRunResponse(BaseModel):
    finding_count: int
    pending_outbox_count: int


def denied() -> ApplicationError:
    return ApplicationError(
        code="tenant_access_denied",
        message="You do not have permission to perform this action.",
        status_code=403,
    )


@router.get("/outbox", response_model=list[OutboxEventResponse])
async def list_outbox(
    session: SessionDependency, context: TenantContextDependency
) -> list[OutboxEventResponse]:
    if not has_permission(context.role, Permission.AUDIT_READ):
        raise denied()
    events = list(
        await session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.organization_id == context.organization_id)
            .order_by(OutboxEvent.created_at.desc(), OutboxEvent.id)
            .limit(100)
        )
    )
    return [
        OutboxEventResponse(
            id=event.id,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            correlation_id=event.correlation_id,
            status=cast(Literal["pending", "processing", "published", "dead"], event.status),
            attempt_count=event.attempt_count,
            max_attempts=event.max_attempts,
            available_at=event.available_at,
            created_at=event.created_at,
            published_at=event.published_at,
        )
        for event in events
    ]


@router.post("/reconcile", response_model=ReconciliationRunResponse)
async def run_reconciliation(
    request: Request, session: SessionDependency, context: TenantContextDependency
) -> ReconciliationRunResponse:
    if not has_permission(context.role, Permission.PAYMENT_REFUND):
        raise denied()
    service = ReconciliationService(session, request.state.request_id)
    count = await service.run(context.organization_id)
    pending = await service.pending_outbox_count(context.organization_id)
    return ReconciliationRunResponse(finding_count=count, pending_outbox_count=pending)


@router.get("/findings", response_model=list[ReconciliationFindingResponse])
async def list_findings(
    request: Request, session: SessionDependency, context: TenantContextDependency
) -> list[ReconciliationFindingResponse]:
    if not has_permission(context.role, Permission.AUDIT_READ):
        raise denied()
    items = await ReconciliationService(session, request.state.request_id).list_findings(
        context.organization_id
    )
    return [
        ReconciliationFindingResponse(
            id=item.id,
            finding_code=item.finding_code,
            aggregate_type=item.aggregate_type,
            aggregate_id=item.aggregate_id,
            status=cast(Literal["open", "resolved"], item.status),
            details=item.details,
            correlation_id=item.correlation_id,
            detected_at=item.detected_at,
        )
        for item in items
    ]
