"""Organization and tenant-scoped business use cases."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.service import normalize_email
from nexus.modules.organizations.domain import (
    InvitationConflictError,
    MembershipRole,
    OrganizationNotFoundError,
    TenantAccessDeniedError,
    TenantContext,
    TenantContextRequiredError,
)
from nexus.modules.organizations.models import Branch, Membership, Organization
from nexus.modules.organizations.repository import OrganizationRepository


class OrganizationService:
    """Apply organization invariants inside one transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = OrganizationRepository(session)

    async def create_organization(
        self, user_id: UUID, name: str, slug: str
    ) -> tuple[Organization, Membership]:
        organization = Organization(
            id=uuid4(), name=name.strip(), slug=slug, created_by_user_id=user_id
        )
        membership = Membership(
            organization_id=organization.id,
            user_id=user_id,
            role="owner",
            status="active",
            accepted_at=datetime.now(UTC),
        )
        self._repository.add(organization)
        await self._session.flush()
        self._repository.add(membership)
        await self._session.flush()
        await self._repository.set_active_organization(user_id, organization.id)
        return organization, membership

    async def list_organizations(
        self, user_id: UUID, query: str | None, page: int, page_size: int
    ) -> tuple[list[tuple[Organization, Membership]], int]:
        return await self._repository.list_organizations(
            user_id, query=query, offset=(page - 1) * page_size, limit=page_size
        )

    async def activate(
        self, user_id: UUID, organization_id: UUID
    ) -> tuple[Organization, Membership]:
        organization = await self._repository.organization_for_member(organization_id, user_id)
        if organization is None:
            raise OrganizationNotFoundError
        membership = await self._repository.membership(organization_id, user_id)
        assert membership is not None
        await self._repository.set_active_organization(user_id, organization_id)
        return organization, membership

    async def resolve_tenant_context(self, user_id: UUID) -> TenantContext:
        result = await self._repository.active_context(user_id)
        if result is None:
            raise TenantContextRequiredError
        context, membership = result
        return TenantContext(
            organization_id=context.organization_id,
            user_id=user_id,
            role=membership.role,  # type: ignore[arg-type]
        )

    async def invite_member(
        self, context: TenantContext, email: str, role: MembershipRole
    ) -> Membership:
        self._require_manager(context)
        user = await self._repository.user_by_email(normalize_email(email))
        if user is None:
            raise InvitationConflictError
        existing = await self._repository.membership(context.organization_id, user.id, lock=True)
        if existing is not None:
            raise InvitationConflictError
        membership = Membership(
            organization_id=context.organization_id,
            user_id=user.id,
            role=role,
            status="pending",
            invited_by_user_id=context.user_id,
        )
        self._repository.add(membership)
        await self._session.flush()
        return membership

    async def accept_invitation(self, user_id: UUID, organization_id: UUID) -> Membership:
        membership = await self._repository.membership(organization_id, user_id, lock=True)
        if membership is None or membership.status != "pending":
            raise OrganizationNotFoundError
        membership.status = "active"
        membership.accepted_at = datetime.now(UTC)
        await self._repository.set_active_organization(user_id, organization_id)
        return membership

    async def create_branch(self, context: TenantContext, name: str, slug: str) -> Branch:
        self._require_manager(context)
        branch = Branch(
            organization_id=context.organization_id,
            name=name.strip(),
            slug=slug,
            is_active=True,
        )
        self._repository.add(branch)
        await self._session.flush()
        return branch

    async def list_branches(
        self,
        context: TenantContext,
        query: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Branch], int]:
        return await self._repository.list_branches(
            context.organization_id,
            query=query,
            is_active=is_active,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def get_branch(self, context: TenantContext, branch_id: UUID) -> Branch:
        branch = await self._repository.branch(context.organization_id, branch_id)
        if branch is None:
            raise OrganizationNotFoundError
        return branch

    async def update_branch(
        self,
        context: TenantContext,
        branch_id: UUID,
        *,
        name: str | None,
        is_active: bool | None,
    ) -> Branch:
        self._require_manager(context)
        branch = await self._repository.branch(context.organization_id, branch_id, lock=True)
        if branch is None:
            raise OrganizationNotFoundError
        if name is not None:
            branch.name = name.strip()
        if is_active is not None:
            branch.is_active = is_active
        return branch

    @staticmethod
    def _require_manager(context: TenantContext) -> None:
        if context.role not in {"owner", "admin"}:
            raise TenantAccessDeniedError
