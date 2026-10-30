"""Tenant-scoped inventory persistence with explicit row locking."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.catalog.models import Product
from nexus.modules.inventory.models import InventoryPolicy, StockLevel, StockMovement
from nexus.modules.organizations.models import Branch


class InventoryRepository:
    """Persist inventory state inside a caller-owned transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, instance: object) -> None:
        self._session.add(instance)

    async def policy_for_update(self, organization_id: UUID) -> InventoryPolicy:
        await self._session.execute(
            insert(InventoryPolicy)
            .values(organization_id=organization_id, allow_negative_stock=False)
            .on_conflict_do_nothing(index_elements=[InventoryPolicy.organization_id])
        )
        policy = await self._session.scalar(
            select(InventoryPolicy)
            .where(InventoryPolicy.organization_id == organization_id)
            .with_for_update()
        )
        assert policy is not None
        return policy

    async def active_branch(self, organization_id: UUID, branch_id: UUID) -> Branch | None:
        return await self._session.scalar(
            select(Branch).where(
                Branch.organization_id == organization_id,
                Branch.id == branch_id,
                Branch.is_active.is_(True),
            )
        )

    async def active_product(self, organization_id: UUID, product_id: UUID) -> Product | None:
        return await self._session.scalar(
            select(Product).where(
                Product.organization_id == organization_id,
                Product.id == product_id,
                Product.deleted_at.is_(None),
            )
        )

    async def stock(
        self, organization_id: UUID, branch_id: UUID, product_id: UUID, *, lock: bool = False
    ) -> StockLevel | None:
        statement = select(StockLevel).where(
            StockLevel.organization_id == organization_id,
            StockLevel.branch_id == branch_id,
            StockLevel.product_id == product_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def transfer_stocks_for_update(
        self, organization_id: UUID, product_id: UUID, branch_ids: tuple[UUID, UUID]
    ) -> dict[UUID, StockLevel]:
        rows = list(
            await self._session.scalars(
                select(StockLevel)
                .where(
                    StockLevel.organization_id == organization_id,
                    StockLevel.product_id == product_id,
                    StockLevel.branch_id.in_(branch_ids),
                )
                .order_by(StockLevel.branch_id)
                .with_for_update()
            )
        )
        return {row.branch_id: row for row in rows}

    async def movement_by_key(
        self, organization_id: UUID, idempotency_key: str
    ) -> StockMovement | None:
        return await self._session.scalar(
            select(StockMovement).where(
                StockMovement.organization_id == organization_id,
                StockMovement.idempotency_key == idempotency_key,
            )
        )

    async def has_negative_stock(self, organization_id: UUID) -> bool:
        count = await self._session.scalar(
            select(func.count())
            .select_from(StockLevel)
            .where(StockLevel.organization_id == organization_id, StockLevel.quantity < 0)
        )
        return bool(count)

    async def list_stock(
        self,
        organization_id: UUID,
        *,
        query: str | None,
        branch_id: UUID | None,
        product_id: UUID | None,
        low_stock: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[StockLevel, Product, Branch]], int]:
        conditions = [StockLevel.organization_id == organization_id]
        if query:
            conditions.append(
                or_(Product.name.ilike(f"%{query}%"), Product.sku.ilike(f"%{query}%"))
            )
        if branch_id:
            conditions.append(StockLevel.branch_id == branch_id)
        if product_id:
            conditions.append(StockLevel.product_id == product_id)
        if low_stock is True:
            conditions.append(StockLevel.quantity <= StockLevel.low_stock_threshold)
        if low_stock is False:
            conditions.append(StockLevel.quantity > StockLevel.low_stock_threshold)
        base = (
            select(StockLevel, Product, Branch)
            .join(Product, Product.id == StockLevel.product_id)
            .join(Branch, Branch.id == StockLevel.branch_id)
        )
        rows = (
            await self._session.execute(
                base.where(*conditions)
                .order_by(Product.name, Branch.name, StockLevel.product_id)
                .offset(offset)
                .limit(limit)
            )
        ).all()
        total = await self._session.scalar(
            select(func.count()).select_from(base.where(*conditions).subquery())
        )
        return [(row[0], row[1], row[2]) for row in rows], int(total or 0)

    async def list_movements(
        self,
        organization_id: UUID,
        *,
        product_id: UUID | None,
        branch_id: UUID | None,
        movement_type: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        offset: int,
        limit: int,
    ) -> tuple[list[StockMovement], int]:
        conditions = [StockMovement.organization_id == organization_id]
        if product_id:
            conditions.append(StockMovement.product_id == product_id)
        if branch_id:
            conditions.append(
                or_(
                    StockMovement.source_branch_id == branch_id,
                    StockMovement.destination_branch_id == branch_id,
                )
            )
        if movement_type:
            conditions.append(StockMovement.movement_type == movement_type)
        if created_from:
            conditions.append(StockMovement.created_at >= created_from)
        if created_to:
            conditions.append(StockMovement.created_at <= created_to)
        rows = list(
            await self._session.scalars(
                select(StockMovement)
                .where(*conditions)
                .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        total = await self._session.scalar(
            select(func.count()).select_from(StockMovement).where(*conditions)
        )
        return rows, int(total or 0)
