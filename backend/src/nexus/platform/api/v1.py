"""Version 1 API router."""

from fastapi import APIRouter

from nexus.modules.auth.router import router as auth_router
from nexus.platform.api.models import ApiInfoResponse

router = APIRouter(tags=["api"])
router.include_router(auth_router)


@router.get("", response_model=ApiInfoResponse, summary="API version metadata")
@router.get("/", response_model=ApiInfoResponse, include_in_schema=False)
async def api_info() -> ApiInfoResponse:
    """Return metadata for the current public API version."""
    return ApiInfoResponse(name="NEXUS AI API", version="v1")
