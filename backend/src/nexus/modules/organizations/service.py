"""Organization and tenant-scoped business use cases."""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.models import User
from nexus.modules.auth.service import normalize_email
from nexus.modules.organizations.domain import (
    InvitationConflictError,
    LastOwnerProtectionError,
    MembershipRole,
    OrganizationNotFoundError,
    Permission,
    TenantAccessDeniedError,
    TenantContext,
    TenantContextRequiredError,
    has_permission,
)
from nexus.modules.organizations.models import (
    Branch,
    Membership,
    Organization,
    OrganizationAuditEvent,
)
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
        self._record_audit(
            organization.id,
            user_id,
            "organization.created",
            "organization",
            organization.id,
            {"initial_role": "owner"},
        )
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
            role=cast(MembershipRole, membership.role),
        )

    async def invite_member(
        self, context: TenantContext, email: str, role: MembershipRole
    ) -> Membership:
        self.require_permission(context, Permission.MEMBER_INVITE)
        self._validate_role_assignment(context.role, None, role)
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
        self._record_audit(
            context.organization_id,
            context.user_id,
            "membership.invited",
            "membership",
            user.id,
            {"role": role},
        )
        return membership

    async def accept_invitation(self, user_id: UUID, organization_id: UUID) -> Membership:
        membership = await self._repository.membership(organization_id, user_id, lock=True)
        if membership is None or membership.status != "pending":
            raise OrganizationNotFoundError
        membership.status = "active"
        membership.accepted_at = datetime.now(UTC)
        await self._repository.set_active_organization(user_id, organization_id)
        self._record_audit(
            organization_id,
            user_id,
            "membership.accepted",
            "membership",
            user_id,
            {"role": membership.role},
        )
        return membership

    async def create_branch(self, context: TenantContext, name: str, slug: str) -> Branch:
        self.require_permission(context, Permission.BRANCH_CREATE)
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
        self.require_permission(context, Permission.BRANCH_READ)
        return await self._repository.list_branches(
            context.organization_id,
            query=query,
            is_active=is_active,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def get_branch(self, context: TenantContext, branch_id: UUID) -> Branch:
        self.require_permission(context, Permission.BRANCH_READ)
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
        self.require_permission(context, Permission.BRANCH_UPDATE)
        branch = await self._repository.branch(context.organization_id, branch_id, lock=True)
        if branch is None:
            raise OrganizationNotFoundError
        if name is not None:
            branch.name = name.strip()
        if is_active is not None:
            branch.is_active = is_active
        return branch

    async def list_members(
        self,
        context: TenantContext,
        query: str | None,
        role: MembershipRole | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[Membership, User]], int]:
        self.require_permission(context, Permission.MEMBER_READ)
        rows, total = await self._repository.list_members(
            context.organization_id,
            query=query,
            role=role,
            status=status,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return rows, total

    async def change_member_role(
        self, context: TenantContext, target_user_id: UUID, new_role: MembershipRole
    ) -> Membership:
        self.require_permission(context, Permission.MEMBER_ROLE_MANAGE)
        membership = await self._repository.membership(
            context.organization_id, target_user_id, lock=True
        )
        if membership is None:
            raise OrganizationNotFoundError
        current_role = cast(MembershipRole, membership.role)
        self._validate_role_assignment(context.role, current_role, new_role)
        if current_role == "owner" and new_role != "owner" and membership.status == "active":
            await self._ensure_not_last_owner(context.organization_id)
        membership.role = new_role
        self._record_audit(
            context.organization_id,
            context.user_id,
            "membership.role_changed",
            "membership",
            target_user_id,
            {"previous_role": current_role, "new_role": new_role},
        )
        return membership

    async def remove_member(self, context: TenantContext, target_user_id: UUID) -> None:
        self.require_permission(context, Permission.MEMBER_REMOVE)
        membership = await self._repository.membership(
            context.organization_id, target_user_id, lock=True
        )
        if membership is None:
            raise OrganizationNotFoundError
        target_role = cast(MembershipRole, membership.role)
        self._validate_member_target(context.role, target_role)
        if target_role == "owner" and membership.status == "active":
            await self._ensure_not_last_owner(context.organization_id)
        self._record_audit(
            context.organization_id,
            context.user_id,
            "membership.removed",
            "membership",
            target_user_id,
            {"previous_role": target_role, "previous_status": membership.status},
        )
        await self._repository.delete_membership(membership)

    async def list_audit_events(
        self,
        context: TenantContext,
        event_type: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[OrganizationAuditEvent], int]:
        self.require_permission(context, Permission.AUDIT_READ)
        return await self._repository.list_audit_events(
            context.organization_id,
            event_type=event_type,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def _ensure_not_last_owner(self, organization_id: UUID) -> None:
        owners = await self._repository.active_owners_for_update(organization_id)
        if len(owners) <= 1:
            raise LastOwnerProtectionError

    @staticmethod
    def _validate_role_assignment(
        actor_role: MembershipRole,
        target_current_role: MembershipRole | None,
        new_role: MembershipRole,
    ) -> None:
        if actor_role == "owner":
            return
        if (
            actor_role == "admin"
            and target_current_role not in {"owner", "admin"}
            and new_role
            not in {
                "owner",
                "admin",
            }
        ):
            return
        raise TenantAccessDeniedError

    @staticmethod
    def _validate_member_target(actor_role: MembershipRole, target_role: MembershipRole) -> None:
        if actor_role == "owner":
            return
        if actor_role == "admin" and target_role not in {"owner", "admin"}:
            return
        raise TenantAccessDeniedError

    def _record_audit(
        self,
        organization_id: UUID,
        actor_user_id: UUID,
        event_type: str,
        target_type: str,
        target_id: UUID | None,
        details: dict[str, object],
    ) -> None:
        self._repository.add(
            OrganizationAuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                event_type=event_type,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
        )

    @staticmethod
    def require_permission(context: TenantContext, permission: Permission) -> None:
        if not has_permission(context.role, permission):
            raise TenantAccessDeniedError
