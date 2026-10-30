"""Operational health endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from nexus.platform.api.dependencies import ReadinessCheck, get_readiness_checks
from nexus.platform.api.models import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse, summary="Liveness probe")
async def live() -> HealthResponse:
    """Report whether the API process can serve requests."""
    return HealthResponse(status="alive")


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
    summary="Readiness probe",
)
async def ready(
    response: Response,
    checks: Annotated[tuple[tuple[str, ReadinessCheck], ...], Depends(get_readiness_checks)],
) -> HealthResponse:
    """Report whether all configured dependencies can serve traffic."""
    results = {name: "up" if await check() else "down" for name, check in checks}
    if any(result == "down" for result in results.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="not_ready", checks=results)
    return HealthResponse(status="ready", checks=results)
