"""Tenant context dependencies resolved from authenticated server state."""

from typing import Annotated

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.dependencies import get_current_user, get_transaction
from nexus.modules.auth.domain import AuthenticatedUser
from nexus.modules.organizations.domain import TenantContext, TenantContextRequiredError
from nexus.modules.organizations.service import OrganizationService
from nexus.platform.api.errors import ApplicationError

SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]
CurrentUserDependency = Annotated[AuthenticatedUser, Depends(get_current_user)]


async def get_tenant_context(
    session: SessionDependency, current_user: CurrentUserDependency
) -> TenantContext:
    """Resolve active tenant exclusively from server-side membership state."""
    try:
        return await OrganizationService(session).resolve_tenant_context(current_user.user_id)
    except TenantContextRequiredError as exc:
        raise ApplicationError(
            code="tenant_context_required",
            message="An active organization is required.",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc


TenantContextDependency = Annotated[TenantContext, Depends(get_tenant_context)]
