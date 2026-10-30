"""Tenant-scoped SQLAlchemy persistence adapter."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.models import User
from nexus.modules.organizations.models import (
    ActiveOrganizationContext,
    Branch,
    Membership,
    Organization,
)


class OrganizationRepository:
    """Persist organization state inside a caller-owned transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def user_by_email(self, email: str) -> User | None:
        return await self._session.scalar(select(User).where(User.email == email))

    async def membership(
        self, organization_id: UUID, user_id: UUID, *, lock: bool = False
    ) -> Membership | None:
        statement = select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def active_context(
        self, user_id: UUID
    ) -> tuple[ActiveOrganizationContext, Membership] | None:
        row = (
            await self._session.execute(
                select(ActiveOrganizationContext, Membership)
                .join(
                    Membership,
                    (Membership.organization_id == ActiveOrganizationContext.organization_id)
                    & (Membership.user_id == ActiveOrganizationContext.user_id),
                )
                .where(
                    ActiveOrganizationContext.user_id == user_id,
                    Membership.status == "active",
                )
            )
        ).one_or_none()
        return None if row is None else (row[0], row[1])

    async def organization_for_member(
        self, organization_id: UUID, user_id: UUID
    ) -> Organization | None:
        return await self._session.scalar(
            select(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(
                Organization.id == organization_id,
                Membership.user_id == user_id,
                Membership.status == "active",
            )
        )

    async def list_organizations(
        self, user_id: UUID, *, query: str | None, offset: int, limit: int
    ) -> tuple[list[tuple[Organization, Membership]], int]:
        conditions = [Membership.user_id == user_id, Membership.status == "active"]
        if query:
            conditions.append(Organization.name.ilike(f"%{query}%"))
        base = select(Organization, Membership).join(
            Membership, Membership.organization_id == Organization.id
        )
        rows = (
            await self._session.execute(
                base.where(*conditions)
                .order_by(Organization.name, Organization.id)
                .offset(offset)
                .limit(limit)
            )
        ).all()
        total = await self._session.scalar(
            select(func.count()).select_from(base.where(*conditions).subquery())
        )
        return [(row[0], row[1]) for row in rows], int(total or 0)

    async def branch(
        self, organization_id: UUID, branch_id: UUID, *, lock: bool = False
    ) -> Branch | None:
        statement = select(Branch).where(
            Branch.organization_id == organization_id,
            Branch.id == branch_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def list_branches(
        self,
        organization_id: UUID,
        *,
        query: str | None,
        is_active: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Branch], int]:
        conditions = [Branch.organization_id == organization_id]
        if query:
            conditions.append(Branch.name.ilike(f"%{query}%"))
        if is_active is not None:
            conditions.append(Branch.is_active == is_active)
        statement = select(Branch).where(*conditions)
        rows = list(
            await self._session.scalars(
                statement.order_by(Branch.name, Branch.id).offset(offset).limit(limit)
            )
        )
        total = await self._session.scalar(
            select(func.count()).select_from(Branch).where(*conditions)
        )
        return rows, int(total or 0)

    def add(self, instance: object) -> None:
        self._session.add(instance)

    async def set_active_organization(self, user_id: UUID, organization_id: UUID) -> None:
        context = await self._session.get(ActiveOrganizationContext, user_id)
        if context is None:
            self.add(ActiveOrganizationContext(user_id=user_id, organization_id=organization_id))
        else:
            context.organization_id = organization_id
            context.selected_at = datetime.now(UTC)
