"""Organization and tenant-scoped branch API routes."""

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.dependencies import get_current_user, get_transaction
from nexus.modules.auth.domain import AuthenticatedUser
from nexus.modules.organizations.dependencies import TenantContextDependency
from nexus.modules.organizations.domain import (
    InvitationConflictError,
    OrganizationNotFoundError,
    TenantAccessDeniedError,
)
from nexus.modules.organizations.models import Branch, Membership, Organization
from nexus.modules.organizations.schemas import (
    BranchCreateRequest,
    BranchPageResponse,
    BranchResponse,
    BranchUpdateRequest,
    InvitationCreateRequest,
    MembershipResponse,
    OrganizationCreateRequest,
    OrganizationPageResponse,
    OrganizationResponse,
)
from nexus.modules.organizations.service import OrganizationService
from nexus.platform.api.errors import ApplicationError

router = APIRouter(tags=["organizations"])
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]
CurrentUserDependency = Annotated[AuthenticatedUser, Depends(get_current_user)]
PageDependency = Annotated[int, Query(ge=1)]
PageSizeDependency = Annotated[int, Query(ge=1, le=100)]


def organization_response(organization: Organization, role: str) -> OrganizationResponse:
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        role=cast(Literal["owner", "admin", "member"], role),
        created_at=organization.created_at,
    )


def membership_response(membership: Membership) -> MembershipResponse:
    return MembershipResponse(
        organization_id=membership.organization_id,
        user_id=membership.user_id,
        role=cast(Literal["owner", "admin", "member"], membership.role),
        status=cast(Literal["pending", "active"], membership.status),
        created_at=membership.created_at,
    )


def branch_response(branch: Branch) -> BranchResponse:
    return BranchResponse(
        id=branch.id,
        name=branch.name,
        slug=branch.slug,
        is_active=branch.is_active,
        created_at=branch.created_at,
    )


def not_found() -> ApplicationError:
    return ApplicationError(
        code="resource_not_found",
        message="The requested resource was not found.",
        status_code=status.HTTP_404_NOT_FOUND,
    )


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    body: OrganizationCreateRequest,
    session: SessionDependency,
    current_user: CurrentUserDependency,
) -> OrganizationResponse:
    try:
        organization, membership = await OrganizationService(session).create_organization(
            current_user.user_id, body.name, body.slug
        )
    except IntegrityError as exc:
        raise ApplicationError(
            code="organization_conflict",
            message="Unable to create the organization.",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc
    return organization_response(organization, membership.role)


@router.get("/organizations", response_model=OrganizationPageResponse)
async def list_organizations(
    session: SessionDependency,
    current_user: CurrentUserDependency,
    page: PageDependency = 1,
    page_size: PageSizeDependency = 20,
    query: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
) -> OrganizationPageResponse:
    items, total = await OrganizationService(session).list_organizations(
        current_user.user_id, query, page, page_size
    )
    return OrganizationPageResponse(
        items=[organization_response(org, membership.role) for org, membership in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/organizations/{organization_id}/activate", response_model=OrganizationResponse)
async def activate_organization(
    organization_id: UUID,
    session: SessionDependency,
    current_user: CurrentUserDependency,
) -> OrganizationResponse:
    try:
        organization, membership = await OrganizationService(session).activate(
            current_user.user_id, organization_id
        )
    except OrganizationNotFoundError as exc:
        raise not_found() from exc
    return organization_response(organization, membership.role)


@router.post(
    "/organizations/current/invitations",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    body: InvitationCreateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> MembershipResponse:
    try:
        membership = await OrganizationService(session).invite_member(
            context, body.email, body.role
        )
    except TenantAccessDeniedError as exc:
        raise ApplicationError(
            code="tenant_access_denied",
            message="You do not have permission to perform this action.",
            status_code=status.HTTP_403_FORBIDDEN,
        ) from exc
    except (InvitationConflictError, IntegrityError) as exc:
        raise ApplicationError(
            code="invitation_unavailable",
            message="Unable to create the invitation.",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc
    return membership_response(membership)


@router.post(
    "/organizations/{organization_id}/invitations/accept",
    response_model=MembershipResponse,
)
async def accept_invitation(
    organization_id: UUID,
    session: SessionDependency,
    current_user: CurrentUserDependency,
) -> MembershipResponse:
    try:
        membership = await OrganizationService(session).accept_invitation(
            current_user.user_id, organization_id
        )
    except OrganizationNotFoundError as exc:
        raise not_found() from exc
    return membership_response(membership)


@router.post("/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def create_branch(
    body: BranchCreateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> BranchResponse:
    try:
        branch = await OrganizationService(session).create_branch(context, body.name, body.slug)
    except TenantAccessDeniedError as exc:
        raise ApplicationError(
            code="tenant_access_denied",
            message="You do not have permission to perform this action.",
            status_code=status.HTTP_403_FORBIDDEN,
        ) from exc
    except IntegrityError as exc:
        raise ApplicationError(
            code="branch_conflict",
            message="Unable to create the branch.",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc
    return branch_response(branch)


@router.get("/branches", response_model=BranchPageResponse)
async def list_branches(
    session: SessionDependency,
    context: TenantContextDependency,
    page: PageDependency = 1,
    page_size: PageSizeDependency = 20,
    query: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    is_active: bool | None = None,
) -> BranchPageResponse:
    items, total = await OrganizationService(session).list_branches(
        context, query, is_active, page, page_size
    )
    return BranchPageResponse(
        items=[branch_response(branch) for branch in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/branches/{branch_id}", response_model=BranchResponse)
async def get_branch(
    branch_id: UUID,
    session: SessionDependency,
    context: TenantContextDependency,
) -> BranchResponse:
    try:
        return branch_response(await OrganizationService(session).get_branch(context, branch_id))
    except OrganizationNotFoundError as exc:
        raise not_found() from exc


@router.patch("/branches/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: UUID,
    body: BranchUpdateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> BranchResponse:
    try:
        branch = await OrganizationService(session).update_branch(
            context, branch_id, name=body.name, is_active=body.is_active
        )
    except OrganizationNotFoundError as exc:
        raise not_found() from exc
    except TenantAccessDeniedError as exc:
        raise ApplicationError(
            code="tenant_access_denied",
            message="You do not have permission to perform this action.",
            status_code=status.HTTP_403_FORBIDDEN,
        ) from exc
    return branch_response(branch)
