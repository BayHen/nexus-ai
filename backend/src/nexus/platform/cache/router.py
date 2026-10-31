"""Authenticated bounded cache metrics endpoint."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from nexus.modules.organizations.dependencies import TenantContextDependency
from nexus.modules.organizations.domain import Permission, has_permission
from nexus.platform.api.errors import ApplicationError
from nexus.platform.cache.service import CacheService

router = APIRouter(prefix="/cache", tags=["cache"])


class CacheMetricsResponse(BaseModel):
    hits: int
    misses: int
    errors: int
    sets: int
    deletes: int


def get_cache(request: Request) -> CacheService:
    return cast(CacheService, request.app.state.cache_service)


CacheDependency = Annotated[CacheService, Depends(get_cache)]


@router.get("/metrics", response_model=CacheMetricsResponse)
async def cache_metrics(
    cache: CacheDependency, context: TenantContextDependency
) -> CacheMetricsResponse:
    if not has_permission(context.role, Permission.AUDIT_READ):
        raise ApplicationError(
            code="tenant_access_denied",
            message="You do not have permission to perform this action.",
            status_code=403,
        )
    return CacheMetricsResponse(**cache.metrics())
