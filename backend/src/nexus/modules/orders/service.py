"""Transaction-safe order workflows with inventory deduction and restoration."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.inventory.models import StockMovement
from nexus.modules.orders.domain import (
    OrderConflictError,
    OrderInsufficientStockError,
    OrderNotFoundError,
)
from nexus.modules.orders.models import Order, OrderItem
from nexus.modules.orders.repository import OrderRepository
from nexus.modules.organizations.domain import (
    Permission,
    TenantAccessDeniedError,
    TenantContext,
    has_permission,
)


class OrderService:
    """Own Order state transitions inside the request transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = OrderRepository(session)

    async def create(self, context: TenantContext) -> tuple[Order, list[OrderItem]]:
        self._authorize(context, Permission.ORDER_WRITE)
        order = Order(
            organization_id=context.organization_id,
            status="draft",
            total_amount=Decimal("0"),
            created_by_user_id=context.user_id,
        )
        self._repository.add(order)
        await self._session.flush()
        return order, []

    async def get(self, context: TenantContext, order_id: UUID) -> tuple[Order, list[OrderItem]]:
        self._authorize(context, Permission.ORDER_READ)
        order = await self._required_order(context.organization_id, order_id)
        return order, await self._repository.items(context.organization_id, order.id)

    async def list_orders(
        self,
        context: TenantContext,
        *,
        status: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[Order, list[OrderItem]]], int]:
        self._authorize(context, Permission.ORDER_READ)
        orders, total = await self._repository.list_orders(
            context.organization_id,
            status=status,
            created_from=created_from,
            created_to=created_to,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return [
            (order, await self._repository.items(context.organization_id, order.id))
            for order in orders
        ], total

    async def add_item(
        self,
        context: TenantContext,
        order_id: UUID,
        *,
        product_id: UUID,
        branch_id: UUID,
        quantity: Decimal,
    ) -> tuple[Order, list[OrderItem]]:
        self._authorize(context, Permission.ORDER_WRITE)
        order = await self._required_order(context.organization_id, order_id, lock=True)
        self._require_draft(order)
        product = await self._repository.active_product(context.organization_id, product_id)
        branch = await self._repository.active_branch(context.organization_id, branch_id)
        if product is None or branch is None:
            raise OrderNotFoundError
        item = OrderItem(
            organization_id=context.organization_id,
            order_id=order.id,
            product_id=product.id,
            branch_id=branch.id,
            product_sku_snapshot=product.sku,
            product_name_snapshot=product.name,
            unit_price_snapshot=product.price,
            quantity=quantity,
            line_total=product.price * quantity,
        )
        self._repository.add(item)
        await self._session.flush()
        await self._repository.recalculate_total(order)
        return order, await self._repository.items(context.organization_id, order.id)

    async def update_item(
        self,
        context: TenantContext,
        order_id: UUID,
        item_id: UUID,
        quantity: Decimal,
    ) -> tuple[Order, list[OrderItem]]:
        self._authorize(context, Permission.ORDER_WRITE)
        order = await self._required_order(context.organization_id, order_id, lock=True)
        self._require_draft(order)
        item = await self._repository.item(context.organization_id, order.id, item_id)
        if item is None:
            raise OrderNotFoundError
        item.quantity = quantity
        item.line_total = item.unit_price_snapshot * quantity
        await self._session.flush()
        await self._repository.recalculate_total(order)
        return order, await self._repository.items(context.organization_id, order.id)

    async def remove_item(
        self, context: TenantContext, order_id: UUID, item_id: UUID
    ) -> tuple[Order, list[OrderItem]]:
        self._authorize(context, Permission.ORDER_WRITE)
        order = await self._required_order(context.organization_id, order_id, lock=True)
        self._require_draft(order)
        item = await self._repository.item(context.organization_id, order.id, item_id)
        if item is None:
            raise OrderNotFoundError
        await self._session.delete(item)
        await self._session.flush()
        await self._repository.recalculate_total(order)
        return order, await self._repository.items(context.organization_id, order.id)

    async def confirm(
        self, context: TenantContext, order_id: UUID
    ) -> tuple[Order, list[OrderItem]]:
        self._authorize(context, Permission.ORDER_CONFIRM)
        order = await self._required_order(context.organization_id, order_id, lock=True)
        self._require_draft(order)
        items = await self._repository.items(context.organization_id, order.id)
        if not items:
            raise OrderConflictError
        stocks = await self._repository.stocks_for_update(context.organization_id, items)
        if len(stocks) != len(items):
            raise OrderInsufficientStockError
        for item in items:
            stock = stocks[(item.branch_id, item.product_id)]
            quantity_after = stock.quantity - item.quantity
            if quantity_after < 0:
                raise OrderInsufficientStockError
            stock.quantity = quantity_after
            self._repository.add(
                StockMovement(
                    organization_id=context.organization_id,
                    product_id=item.product_id,
                    destination_branch_id=item.branch_id,
                    movement_type="adjustment",
                    quantity_delta=-item.quantity,
                    destination_quantity_after=quantity_after,
                    idempotency_key=f"order:{order.id}:confirm:{item.id}",
                    request_fingerprint=str(order.id),
                    reference=f"ORDER:{order.id}",
                    reason="Order confirmation",
                    actor_user_id=context.user_id,
                )
            )
        transitioned_at = datetime.now(UTC)
        order.status = "confirmed"
        order.confirmed_at = transitioned_at
        order.updated_at = transitioned_at
        await self._session.flush()
        return order, items

    async def cancel(self, context: TenantContext, order_id: UUID) -> tuple[Order, list[OrderItem]]:
        self._authorize(context, Permission.ORDER_CANCEL)
        order = await self._required_order(context.organization_id, order_id, lock=True)
        if order.status not in {"draft", "confirmed"}:
            raise OrderConflictError
        items = await self._repository.items(context.organization_id, order.id)
        if order.status == "confirmed":
            stocks = await self._repository.stocks_for_update(context.organization_id, items)
            if len(stocks) != len(items):
                raise OrderConflictError
            for item in items:
                stock = stocks[(item.branch_id, item.product_id)]
                quantity_after = stock.quantity + item.quantity
                stock.quantity = quantity_after
                self._repository.add(
                    StockMovement(
                        organization_id=context.organization_id,
                        product_id=item.product_id,
                        destination_branch_id=item.branch_id,
                        movement_type="adjustment",
                        quantity_delta=item.quantity,
                        destination_quantity_after=quantity_after,
                        idempotency_key=f"order:{order.id}:cancel:{item.id}",
                        request_fingerprint=str(order.id),
                        reference=f"ORDER:{order.id}",
                        reason="Order cancellation",
                        actor_user_id=context.user_id,
                    )
                )
        transitioned_at = datetime.now(UTC)
        order.status = "cancelled"
        order.cancelled_at = transitioned_at
        order.updated_at = transitioned_at
        await self._session.flush()
        return order, items

    async def _required_order(
        self, organization_id: UUID, order_id: UUID, *, lock: bool = False
    ) -> Order:
        order = await self._repository.order(organization_id, order_id, lock=lock)
        if order is None:
            raise OrderNotFoundError
        return order

    @staticmethod
    def _require_draft(order: Order) -> None:
        if order.status != "draft":
            raise OrderConflictError

    @staticmethod
    def _authorize(context: TenantContext, permission: Permission) -> None:
        if not has_permission(context.role, permission):
            raise TenantAccessDeniedError
