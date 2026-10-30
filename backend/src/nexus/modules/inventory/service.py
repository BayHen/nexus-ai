"""Transaction-safe inventory workflows."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.catalog.models import Product
from nexus.modules.inventory.domain import (
    InsufficientStockError,
    InvalidTransferError,
    InventoryConflictError,
    InventoryNotFoundError,
)
from nexus.modules.inventory.models import InventoryPolicy, StockLevel, StockMovement
from nexus.modules.inventory.repository import InventoryRepository
from nexus.modules.organizations.domain import (
    Permission,
    TenantAccessDeniedError,
    TenantContext,
    has_permission,
)
from nexus.modules.organizations.models import Branch


class InventoryService:
    """Serialize stock mutations and append an immutable ledger entry."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = InventoryRepository(session)

    async def create_stock(
        self,
        context: TenantContext,
        branch_id: UUID,
        product_id: UUID,
        threshold: Decimal,
    ) -> StockLevel:
        self._authorize(context, Permission.INVENTORY_MANAGE)
        if await self._repository.active_branch(context.organization_id, branch_id) is None:
            raise InventoryNotFoundError
        if await self._repository.active_product(context.organization_id, product_id) is None:
            raise InventoryNotFoundError
        await self._repository.policy_for_update(context.organization_id)
        stock = StockLevel(
            organization_id=context.organization_id,
            branch_id=branch_id,
            product_id=product_id,
            quantity=Decimal("0"),
            low_stock_threshold=threshold,
        )
        self._repository.add(stock)
        await self._session.flush()
        return stock

    async def update_threshold(
        self, context: TenantContext, branch_id: UUID, product_id: UUID, threshold: Decimal
    ) -> StockLevel:
        self._authorize(context, Permission.INVENTORY_MANAGE)
        stock = await self._repository.stock(
            context.organization_id, branch_id, product_id, lock=True
        )
        if stock is None:
            raise InventoryNotFoundError
        stock.low_stock_threshold = threshold
        return stock

    async def list_stock(
        self,
        context: TenantContext,
        *,
        query: str | None,
        branch_id: UUID | None,
        product_id: UUID | None,
        low_stock: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[StockLevel, Product, Branch]], int]:
        self._authorize(context, Permission.INVENTORY_READ)
        return await self._repository.list_stock(
            context.organization_id,
            query=query,
            branch_id=branch_id,
            product_id=product_id,
            low_stock=low_stock,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def list_movements(
        self,
        context: TenantContext,
        *,
        product_id: UUID | None,
        branch_id: UUID | None,
        movement_type: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[StockMovement], int]:
        self._authorize(context, Permission.INVENTORY_READ)
        return await self._repository.list_movements(
            context.organization_id,
            product_id=product_id,
            branch_id=branch_id,
            movement_type=movement_type,
            created_from=created_from,
            created_to=created_to,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def get_policy(self, context: TenantContext) -> InventoryPolicy:
        self._authorize(context, Permission.INVENTORY_READ)
        return await self._repository.policy_for_update(context.organization_id)

    async def update_policy(
        self, context: TenantContext, allow_negative_stock: bool
    ) -> InventoryPolicy:
        self._authorize(context, Permission.INVENTORY_POLICY)
        policy = await self._repository.policy_for_update(context.organization_id)
        if not allow_negative_stock and await self._repository.has_negative_stock(
            context.organization_id
        ):
            raise InventoryConflictError
        policy.allow_negative_stock = allow_negative_stock
        return policy

    async def adjust(
        self,
        context: TenantContext,
        *,
        branch_id: UUID,
        product_id: UUID,
        quantity_delta: Decimal,
        reason: str,
        reference: str | None,
        idempotency_key: str,
    ) -> tuple[StockMovement, bool]:
        self._authorize(context, Permission.INVENTORY_ADJUST)
        fingerprint = self._fingerprint(
            "adjustment", branch_id, product_id, quantity_delta, reason, reference
        )
        existing = await self._repository.movement_by_key(context.organization_id, idempotency_key)
        if existing is not None:
            return self._replay(existing, fingerprint)
        policy = await self._repository.policy_for_update(context.organization_id)
        stock = await self._repository.stock(
            context.organization_id, branch_id, product_id, lock=True
        )
        if stock is None:
            raise InventoryNotFoundError
        existing = await self._repository.movement_by_key(context.organization_id, idempotency_key)
        if existing is not None:
            return self._replay(existing, fingerprint)
        new_quantity = stock.quantity + quantity_delta
        if new_quantity < 0 and not policy.allow_negative_stock:
            raise InsufficientStockError
        stock.quantity = new_quantity
        movement = StockMovement(
            organization_id=context.organization_id,
            product_id=product_id,
            destination_branch_id=branch_id,
            movement_type="adjustment",
            quantity_delta=quantity_delta,
            destination_quantity_after=new_quantity,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            reference=reference,
            reason=reason,
            actor_user_id=context.user_id,
        )
        self._repository.add(movement)
        await self._session.flush()
        return movement, False

    async def transfer(
        self,
        context: TenantContext,
        *,
        source_branch_id: UUID,
        destination_branch_id: UUID,
        product_id: UUID,
        quantity: Decimal,
        reason: str,
        reference: str | None,
        idempotency_key: str,
    ) -> tuple[StockMovement, bool]:
        self._authorize(context, Permission.INVENTORY_ADJUST)
        if source_branch_id == destination_branch_id:
            raise InvalidTransferError
        fingerprint = self._fingerprint(
            "transfer",
            source_branch_id,
            destination_branch_id,
            product_id,
            quantity,
            reason,
            reference,
        )
        existing = await self._repository.movement_by_key(context.organization_id, idempotency_key)
        if existing is not None:
            return self._replay(existing, fingerprint)
        policy = await self._repository.policy_for_update(context.organization_id)
        ordered_branch_ids = sorted((source_branch_id, destination_branch_id), key=str)
        branch_ids = (ordered_branch_ids[0], ordered_branch_ids[1])
        stocks = await self._repository.transfer_stocks_for_update(
            context.organization_id, product_id, branch_ids
        )
        if len(stocks) != 2:
            raise InventoryNotFoundError
        existing = await self._repository.movement_by_key(context.organization_id, idempotency_key)
        if existing is not None:
            return self._replay(existing, fingerprint)
        source = stocks[source_branch_id]
        destination = stocks[destination_branch_id]
        source_after = source.quantity - quantity
        if source_after < 0 and not policy.allow_negative_stock:
            raise InsufficientStockError
        destination_after = destination.quantity + quantity
        source.quantity = source_after
        destination.quantity = destination_after
        movement = StockMovement(
            organization_id=context.organization_id,
            product_id=product_id,
            source_branch_id=source_branch_id,
            destination_branch_id=destination_branch_id,
            movement_type="transfer",
            quantity_delta=quantity,
            source_quantity_after=source_after,
            destination_quantity_after=destination_after,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            reference=reference,
            reason=reason,
            actor_user_id=context.user_id,
        )
        self._repository.add(movement)
        await self._session.flush()
        return movement, False

    @staticmethod
    def _replay(movement: StockMovement, fingerprint: str) -> tuple[StockMovement, bool]:
        if movement.request_fingerprint != fingerprint:
            raise InventoryConflictError
        return movement, True

    @staticmethod
    def _fingerprint(*parts: object) -> str:
        payload = json.dumps([str(part) if part is not None else None for part in parts])
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _authorize(context: TenantContext, permission: Permission) -> None:
        if not has_permission(context.role, permission):
            raise TenantAccessDeniedError
