"""Tenant-scoped background job status and bounded monitoring APIs."""

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.dependencies import get_transaction
from nexus.modules.organizations.dependencies import TenantContextDependency
from nexus.modules.organizations.domain import Permission, has_permission
from nexus.platform.api.errors import ApplicationError
from nexus.platform.background.models import BackgroundJob

router = APIRouter(prefix="/background", tags=["background"])
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]


class JobStatusResponse(BaseModel):
    id: UUID
    task_name: str
    status: Literal["queued", "running", "retrying", "succeeded", "failed", "dead"]
    attempt_count: int
    max_attempts: int
    error_code: str | None
    correlation_id: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class JobMetricsResponse(BaseModel):
    queued: int = 0
    running: int = 0
    retrying: int = 0
    succeeded: int = 0
    failed: int = 0
    dead: int = 0


def denied() -> ApplicationError:
    return ApplicationError(
        code="tenant_access_denied",
        message="You do not have permission to perform this action.",
        status_code=403,
    )


def to_response(job: BackgroundJob) -> JobStatusResponse:
    return JobStatusResponse(
        id=job.id,
        task_name=job.task_name,
        status=cast(
            Literal["queued", "running", "retrying", "succeeded", "failed", "dead"],
            job.status,
        ),
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        error_code=job.error_code,
        correlation_id=job.correlation_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


@router.get("/jobs", response_model=list[JobStatusResponse])
async def list_jobs(
    session: SessionDependency, context: TenantContextDependency
) -> list[JobStatusResponse]:
    if not has_permission(context.role, Permission.AUDIT_READ):
        raise denied()
    jobs = list(
        await session.scalars(
            select(BackgroundJob)
            .where(BackgroundJob.organization_id == context.organization_id)
            .order_by(BackgroundJob.created_at.desc(), BackgroundJob.id)
            .limit(100)
        )
    )
    return [to_response(job) for job in jobs]


@router.get("/metrics", response_model=JobMetricsResponse)
async def job_metrics(
    session: SessionDependency, context: TenantContextDependency
) -> JobMetricsResponse:
    if not has_permission(context.role, Permission.AUDIT_READ):
        raise denied()
    rows = (
        await session.execute(
            select(BackgroundJob.status, func.count())
            .where(BackgroundJob.organization_id == context.organization_id)
            .group_by(BackgroundJob.status)
        )
    ).all()
    counts = {str(status): int(count) for status, count in rows}
    return JobMetricsResponse(**counts)
