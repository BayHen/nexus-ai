"""Tenant-scoped REST analytics and asynchronous export APIs."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.analytics.models import AnalyticsExport
from nexus.modules.analytics.schemas import (
    AnalyticsExportRequest,
    AnalyticsExportResponse,
    AnalyticsSummaryResponse,
    BestSellingProductsResponse,
    BranchRevenueResponse,
    InventoryValuationResponse,
    RevenueSeriesResponse,
)
from nexus.modules.analytics.service import AnalyticsService
from nexus.modules.auth.dependencies import get_transaction
from nexus.modules.organizations.dependencies import TenantContextDependency
from nexus.modules.organizations.domain import Permission, has_permission
from nexus.platform.api.errors import ApplicationError
from nexus.platform.background.service import ANALYTICS_EXPORT_JOB, JobScheduler
from nexus.platform.background.tasks import dispatch_job

router = APIRouter(prefix="/analytics", tags=["analytics"])
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]
CurrencyDependency = Annotated[str, Query(pattern=r"^[A-Z]{3}$")]


def ensure_access(context: TenantContextDependency) -> None:
    if not has_permission(context.role, Permission.AUDIT_READ):
        raise ApplicationError(
            code="tenant_access_denied",
            message="You do not have permission to perform this action.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def ensure_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ApplicationError(
            code="invalid_date_range",
            message="date_from cannot be later than date_to.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def summary(
    session: SessionDependency,
    context: TenantContextDependency,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: CurrencyDependency = "USD",
) -> AnalyticsSummaryResponse:
    ensure_access(context)
    ensure_range(date_from, date_to)
    result = await AnalyticsService(session).summary(
        context.organization_id, currency, date_from, date_to
    )
    return AnalyticsSummaryResponse.model_validate(result)


@router.get("/revenue", response_model=RevenueSeriesResponse)
async def revenue_series(
    session: SessionDependency,
    context: TenantContextDependency,
    granularity: Literal["day", "month"] = "day",
    date_from: date | None = None,
    date_to: date | None = None,
    currency: CurrencyDependency = "USD",
) -> RevenueSeriesResponse:
    ensure_access(context)
    ensure_range(date_from, date_to)
    items = await AnalyticsService(session).revenue_series(
        context.organization_id, currency, date_from, date_to, granularity
    )
    return RevenueSeriesResponse(currency=currency, granularity=granularity, items=items)


@router.get("/products/best-selling", response_model=BestSellingProductsResponse)
async def best_selling_products(
    session: SessionDependency,
    context: TenantContextDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: CurrencyDependency = "USD",
) -> BestSellingProductsResponse:
    ensure_access(context)
    ensure_range(date_from, date_to)
    items = await AnalyticsService(session).best_selling_products(
        context.organization_id, currency, date_from, date_to, limit
    )
    return BestSellingProductsResponse(currency=currency, items=items)


@router.get("/inventory-valuation", response_model=InventoryValuationResponse)
async def inventory_valuation(
    session: SessionDependency,
    context: TenantContextDependency,
    currency: CurrencyDependency = "USD",
) -> InventoryValuationResponse:
    ensure_access(context)
    result = await AnalyticsService(session).inventory_valuation(
        context.organization_id, currency
    )
    return InventoryValuationResponse.model_validate(result)


@router.get("/revenue/branches", response_model=BranchRevenueResponse)
async def branch_revenue(
    session: SessionDependency,
    context: TenantContextDependency,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: CurrencyDependency = "USD",
) -> BranchRevenueResponse:
    ensure_access(context)
    ensure_range(date_from, date_to)
    items = await AnalyticsService(session).branch_revenue(
        context.organization_id, currency, date_from, date_to
    )
    return BranchRevenueResponse(currency=currency, items=items)


@router.post(
    "/exports",
    response_model=AnalyticsExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_export(
    body: AnalyticsExportRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDependency,
    context: TenantContextDependency,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
) -> AnalyticsExportResponse:
    ensure_access(context)
    ensure_range(body.date_from, body.date_to)
    job, created = await JobScheduler(session).schedule(
        organization_id=context.organization_id,
        task_name=ANALYTICS_EXPORT_JOB,
        idempotency_key=idempotency_key,
        payload={
            "file_format": body.file_format,
            "date_from": body.date_from.isoformat() if body.date_from else None,
            "date_to": body.date_to.isoformat() if body.date_to else None,
            "currency": body.currency,
        },
        correlation_id=request.state.request_id,
        max_attempts=request.app.state.settings.background_job_max_attempts,
    )
    await session.flush()
    if created:
        background_tasks.add_task(dispatch_job, job.id)
    return AnalyticsExportResponse(job_id=job.id, status=job.status, created=created)


@router.get("/exports/{job_id}/download", response_class=Response)
async def download_export(
    job_id: UUID,
    session: SessionDependency,
    context: TenantContextDependency,
) -> Response:
    ensure_access(context)
    artifact = await session.scalar(
        select(AnalyticsExport).where(
            AnalyticsExport.job_id == job_id,
            AnalyticsExport.organization_id == context.organization_id,
        )
    )
    if artifact is None:
        raise ApplicationError(
            code="analytics_export_not_found",
            message="The analytics export is not available.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return Response(
        content=artifact.content,
        media_type=artifact.content_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )
