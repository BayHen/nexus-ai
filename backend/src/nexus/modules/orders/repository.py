"""Tenant-scoped order persistence and locking operations."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.catalog.models import Product
from nexus.modules.inventory.models import StockLevel
from nexus.modules.orders.models import Order, OrderItem
from nexus.modules.organizations.models import Branch


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, instance: object) -> None:
        self._session.add(instance)

    async def order(
        self, organization_id: UUID, order_id: UUID, *, lock: bool = False
    ) -> Order | None:
        statement = select(Order).where(
            Order.organization_id == organization_id, Order.id == order_id
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def item(self, organization_id: UUID, order_id: UUID, item_id: UUID) -> OrderItem | None:
        return await self._session.scalar(
            select(OrderItem).where(
                OrderItem.organization_id == organization_id,
                OrderItem.order_id == order_id,
                OrderItem.id == item_id,
            )
        )

    async def items(self, organization_id: UUID, order_id: UUID) -> list[OrderItem]:
        return list(
            await self._session.scalars(
                select(OrderItem)
                .where(
                    OrderItem.organization_id == organization_id,
                    OrderItem.order_id == order_id,
                )
                .order_by(OrderItem.created_at, OrderItem.id)
            )
        )

    async def active_product(self, organization_id: UUID, product_id: UUID) -> Product | None:
        return await self._session.scalar(
            select(Product).where(
                Product.organization_id == organization_id,
                Product.id == product_id,
                Product.deleted_at.is_(None),
                Product.status == "active",
            )
        )

    async def active_branch(self, organization_id: UUID, branch_id: UUID) -> Branch | None:
        return await self._session.scalar(
            select(Branch).where(
                Branch.organization_id == organization_id,
                Branch.id == branch_id,
                Branch.is_active.is_(True),
            )
        )

    async def stocks_for_update(
        self, organization_id: UUID, items: list[OrderItem]
    ) -> dict[tuple[UUID, UUID], StockLevel]:
        keys = sorted(
            {(item.branch_id, item.product_id) for item in items},
            key=lambda key: (str(key[0]), str(key[1])),
        )
        rows: dict[tuple[UUID, UUID], StockLevel] = {}
        for branch_id, product_id in keys:
            stock = await self._session.scalar(
                select(StockLevel)
                .where(
                    StockLevel.organization_id == organization_id,
                    StockLevel.branch_id == branch_id,
                    StockLevel.product_id == product_id,
                )
                .with_for_update()
            )
            if stock is not None:
                rows[(branch_id, product_id)] = stock
        return rows

    async def list_orders(
        self,
        organization_id: UUID,
        *,
        status: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Order], int]:
        conditions = [Order.organization_id == organization_id]
        if status:
            conditions.append(Order.status == status)
        if created_from:
            conditions.append(Order.created_at >= created_from)
        if created_to:
            conditions.append(Order.created_at <= created_to)
        rows = list(
            await self._session.scalars(
                select(Order)
                .where(*conditions)
                .order_by(Order.created_at.desc(), Order.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        total = await self._session.scalar(
            select(func.count()).select_from(Order).where(*conditions)
        )
        return rows, int(total or 0)

    async def recalculate_total(self, order: Order) -> None:
        total = await self._session.scalar(
            select(func.coalesce(func.sum(OrderItem.line_total), 0)).where(
                OrderItem.organization_id == order.organization_id,
                OrderItem.order_id == order.id,
            )
        )
        order.total_amount = Decimal(total or 0)
