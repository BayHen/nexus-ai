"""Internal Prometheus scrape endpoint."""

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(include_in_schema=False)


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    """Expose aggregate operational metrics without business identifiers."""
    payload = generate_latest(request.app.state.telemetry.metrics.registry)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
