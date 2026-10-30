"""Tenant-scoped inventory REST APIs."""

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.dependencies import get_transaction
from nexus.modules.inventory.domain import (
    InsufficientStockError,
    InvalidTransferError,
    InventoryConflictError,
    InventoryNotFoundError,
)
from nexus.modules.inventory.models import StockMovement
from nexus.modules.inventory.schemas import (
    AdjustmentRequest,
    InventoryPolicyResponse,
    InventoryPolicyUpdateRequest,
    MovementPageResponse,
    MovementResponse,
    StockCreateRequest,
    StockPageResponse,
    StockResponse,
    ThresholdUpdateRequest,
    TransferRequest,
)
from nexus.modules.inventory.service import InventoryService
from nexus.modules.organizations.dependencies import TenantContextDependency
from nexus.modules.organizations.domain import TenantAccessDeniedError
from nexus.platform.api.errors import ApplicationError

router = APIRouter(prefix="/inventory", tags=["inventory"])
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]
PageDependency = Annotated[int, Query(ge=1)]
PageSizeDependency = Annotated[int, Query(ge=1, le=100)]


def movement_response(movement: StockMovement, replayed: bool = False) -> MovementResponse:
    return MovementResponse(
        id=movement.id,
        movement_type=cast(Literal["adjustment", "transfer"], movement.movement_type),
        product_id=movement.product_id,
        source_branch_id=movement.source_branch_id,
        destination_branch_id=movement.destination_branch_id,
        quantity_delta=movement.quantity_delta,
        source_quantity_after=movement.source_quantity_after,
        destination_quantity_after=movement.destination_quantity_after,
        reference=movement.reference,
        reason=movement.reason,
        actor_user_id=movement.actor_user_id,
        created_at=movement.created_at,
        replayed=replayed,
    )


def error(code: str, message: str, status_code: int) -> ApplicationError:
    return ApplicationError(code=code, message=message, status_code=status_code)


@router.post("/stocks", response_model=StockResponse, status_code=201)
async def create_stock(
    body: StockCreateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> StockResponse:
    try:
        stock = await InventoryService(session).create_stock(
            context, body.branch_id, body.product_id, body.low_stock_threshold
        )
    except InventoryNotFoundError as exc:
        raise error("resource_not_found", "The requested resource was not found.", 404) from exc
    except TenantAccessDeniedError as exc:
        raise error(
            "tenant_access_denied", "You do not have permission to perform this action.", 403
        ) from exc
    except IntegrityError as exc:
        raise error("inventory_conflict", "The stock record already exists.", 409) from exc
    return StockResponse(
        branch_id=stock.branch_id,
        branch_name=None,
        product_id=stock.product_id,
        product_name=None,
        product_sku=None,
        quantity=stock.quantity,
        low_stock_threshold=stock.low_stock_threshold,
        is_low_stock=stock.quantity <= stock.low_stock_threshold,
        updated_at=stock.updated_at,
    )


@router.get("/stocks", response_model=StockPageResponse)
async def list_stock(
    session: SessionDependency,
    context: TenantContextDependency,
    page: PageDependency = 1,
    page_size: PageSizeDependency = 20,
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    branch_id: UUID | None = None,
    product_id: UUID | None = None,
    low_stock: bool | None = None,
) -> StockPageResponse:
    try:
        rows, total = await InventoryService(session).list_stock(
            context,
            query=query,
            branch_id=branch_id,
            product_id=product_id,
            low_stock=low_stock,
            page=page,
            page_size=page_size,
        )
    except TenantAccessDeniedError as exc:
        raise error(
            "tenant_access_denied", "You do not have permission to perform this action.", 403
        ) from exc
    return StockPageResponse(
        items=[
            StockResponse(
                branch_id=stock.branch_id,
                branch_name=branch.name,
                product_id=stock.product_id,
                product_name=product.name,
                product_sku=product.sku,
                quantity=stock.quantity,
                low_stock_threshold=stock.low_stock_threshold,
                is_low_stock=stock.quantity <= stock.low_stock_threshold,
                updated_at=stock.updated_at,
            )
            for stock, product, branch in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch("/stocks/{branch_id}/{product_id}", response_model=StockResponse)
async def update_threshold(
    branch_id: UUID,
    product_id: UUID,
    body: ThresholdUpdateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> StockResponse:
    try:
        stock = await InventoryService(session).update_threshold(
            context, branch_id, product_id, body.low_stock_threshold
        )
    except InventoryNotFoundError as exc:
        raise error("resource_not_found", "The requested resource was not found.", 404) from exc
    except TenantAccessDeniedError as exc:
        raise error(
            "tenant_access_denied", "You do not have permission to perform this action.", 403
        ) from exc
    return StockResponse(
        branch_id=stock.branch_id,
        branch_name=None,
        product_id=stock.product_id,
        product_name=None,
        product_sku=None,
        quantity=stock.quantity,
        low_stock_threshold=stock.low_stock_threshold,
        is_low_stock=stock.quantity <= stock.low_stock_threshold,
        updated_at=stock.updated_at,
    )


@router.post("/adjustments", response_model=MovementResponse, status_code=201)
async def adjust_stock(
    body: AdjustmentRequest,
    idempotency_key: IdempotencyKey,
    session: SessionDependency,
    context: TenantContextDependency,
) -> MovementResponse:
    try:
        movement, replayed = await InventoryService(session).adjust(
            context,
            branch_id=body.branch_id,
            product_id=body.product_id,
            quantity_delta=body.quantity_delta,
            reason=body.reason,
            reference=body.reference,
            idempotency_key=idempotency_key,
        )
    except InventoryNotFoundError as exc:
        raise error("resource_not_found", "The stock record was not found.", 404) from exc
    except InsufficientStockError as exc:
        raise error(
            "insufficient_stock", "The operation would create negative stock.", 409
        ) from exc
    except InventoryConflictError as exc:
        raise error("idempotency_conflict", "The idempotency key was already used.", 409) from exc
    except TenantAccessDeniedError as exc:
        raise error(
            "tenant_access_denied", "You do not have permission to perform this action.", 403
        ) from exc
    return movement_response(movement, replayed)


@router.post("/transfers", response_model=MovementResponse, status_code=201)
async def transfer_stock(
    body: TransferRequest,
    idempotency_key: IdempotencyKey,
    session: SessionDependency,
    context: TenantContextDependency,
) -> MovementResponse:
    try:
        movement, replayed = await InventoryService(session).transfer(
            context,
            source_branch_id=body.source_branch_id,
            destination_branch_id=body.destination_branch_id,
            product_id=body.product_id,
            quantity=body.quantity,
            reason=body.reason,
            reference=body.reference,
            idempotency_key=idempotency_key,
        )
    except InventoryNotFoundError as exc:
        raise error("resource_not_found", "The stock record was not found.", 404) from exc
    except InsufficientStockError as exc:
        raise error("insufficient_stock", "The transfer would create negative stock.", 409) from exc
    except InvalidTransferError as exc:
        raise error(
            "invalid_transfer", "Source and destination branches must differ.", 422
        ) from exc
    except InventoryConflictError as exc:
        raise error("idempotency_conflict", "The idempotency key was already used.", 409) from exc
    except TenantAccessDeniedError as exc:
        raise error(
            "tenant_access_denied", "You do not have permission to perform this action.", 403
        ) from exc
    return movement_response(movement, replayed)


@router.get("/movements", response_model=MovementPageResponse)
async def list_movements(
    session: SessionDependency,
    context: TenantContextDependency,
    page: PageDependency = 1,
    page_size: PageSizeDependency = 20,
    product_id: UUID | None = None,
    branch_id: UUID | None = None,
    movement_type: Literal["adjustment", "transfer"] | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> MovementPageResponse:
    try:
        items, total = await InventoryService(session).list_movements(
            context,
            product_id=product_id,
            branch_id=branch_id,
            movement_type=movement_type,
            created_from=created_from,
            created_to=created_to,
            page=page,
            page_size=page_size,
        )
    except TenantAccessDeniedError as exc:
        raise error(
            "tenant_access_denied", "You do not have permission to perform this action.", 403
        ) from exc
    return MovementPageResponse(
        items=[movement_response(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/policy", response_model=InventoryPolicyResponse)
async def get_policy(
    session: SessionDependency, context: TenantContextDependency
) -> InventoryPolicyResponse:
    policy = await InventoryService(session).get_policy(context)
    return InventoryPolicyResponse(
        allow_negative_stock=policy.allow_negative_stock, updated_at=policy.updated_at
    )


@router.patch("/policy", response_model=InventoryPolicyResponse)
async def update_policy(
    body: InventoryPolicyUpdateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> InventoryPolicyResponse:
    try:
        policy = await InventoryService(session).update_policy(context, body.allow_negative_stock)
    except InventoryConflictError as exc:
        raise error("inventory_conflict", "Negative stock must be resolved first.", 409) from exc
    except TenantAccessDeniedError as exc:
        raise error(
            "tenant_access_denied", "You do not have permission to perform this action.", 403
        ) from exc
    return InventoryPolicyResponse(
        allow_negative_stock=policy.allow_negative_stock, updated_at=policy.updated_at
    )
