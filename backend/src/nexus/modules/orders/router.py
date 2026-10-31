"""Tenant-scoped Order REST endpoints."""

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.dependencies import get_transaction
from nexus.modules.orders.domain import (
    OrderConflictError,
    OrderInsufficientStockError,
    OrderNotFoundError,
)
from nexus.modules.orders.models import Order, OrderItem
from nexus.modules.orders.schemas import (
    OrderItemCreateRequest,
    OrderItemResponse,
    OrderItemUpdateRequest,
    OrderPageResponse,
    OrderResponse,
)
from nexus.modules.orders.service import OrderService
from nexus.modules.organizations.dependencies import TenantContextDependency
from nexus.modules.organizations.domain import TenantAccessDeniedError
from nexus.platform.api.errors import ApplicationError

router = APIRouter(prefix="/orders", tags=["orders"])
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]
PageDependency = Annotated[int, Query(ge=1)]
PageSizeDependency = Annotated[int, Query(ge=1, le=100)]


def response(order: Order, items: list[OrderItem]) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        status=cast(Literal["draft", "confirmed", "cancelled"], order.status),
        total_amount=order.total_amount,
        items=[OrderItemResponse.model_validate(item) for item in items],
        created_by_user_id=order.created_by_user_id,
        confirmed_at=order.confirmed_at,
        cancelled_at=order.cancelled_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def api_error(code: str, message: str, status_code: int) -> ApplicationError:
    return ApplicationError(code=code, message=message, status_code=status_code)


def translate(exc: Exception) -> ApplicationError:
    if isinstance(exc, OrderNotFoundError):
        return api_error("resource_not_found", "The requested order resource was not found.", 404)
    if isinstance(exc, OrderInsufficientStockError):
        return api_error("insufficient_stock", "The order cannot be fulfilled from stock.", 409)
    if isinstance(exc, OrderConflictError):
        return api_error(
            "invalid_order_state", "The order operation is not valid in its current state.", 409
        )
    if isinstance(exc, TenantAccessDeniedError):
        return api_error(
            "tenant_access_denied", "You do not have permission to perform this action.", 403
        )
    return api_error("order_conflict", "The order conflicts with existing data.", 409)


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    session: SessionDependency, context: TenantContextDependency
) -> OrderResponse:
    try:
        order, items = await OrderService(session).create(context)
    except TenantAccessDeniedError as exc:
        raise translate(exc) from exc
    return response(order, items)


@router.get("", response_model=OrderPageResponse)
async def list_orders(
    session: SessionDependency,
    context: TenantContextDependency,
    page: PageDependency = 1,
    page_size: PageSizeDependency = 20,
    order_status: Annotated[
        Literal["draft", "confirmed", "cancelled"] | None, Query(alias="status")
    ] = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> OrderPageResponse:
    if created_from and created_to and created_from > created_to:
        raise api_error("invalid_date_range", "created_from cannot exceed created_to.", 422)
    try:
        rows, total = await OrderService(session).list_orders(
            context,
            status=order_status,
            created_from=created_from,
            created_to=created_to,
            page=page,
            page_size=page_size,
        )
    except TenantAccessDeniedError as exc:
        raise translate(exc) from exc
    return OrderPageResponse(
        items=[response(order, items) for order, items in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID, session: SessionDependency, context: TenantContextDependency
) -> OrderResponse:
    try:
        order, items = await OrderService(session).get(context, order_id)
    except (OrderNotFoundError, TenantAccessDeniedError) as exc:
        raise translate(exc) from exc
    return response(order, items)


@router.post("/{order_id}/items", response_model=OrderResponse, status_code=201)
async def add_item(
    order_id: UUID,
    body: OrderItemCreateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> OrderResponse:
    try:
        order, items = await OrderService(session).add_item(
            context,
            order_id,
            product_id=body.product_id,
            branch_id=body.branch_id,
            quantity=body.quantity,
        )
    except (OrderNotFoundError, OrderConflictError, TenantAccessDeniedError, IntegrityError) as exc:
        raise translate(exc) from exc
    return response(order, items)


@router.patch("/{order_id}/items/{item_id}", response_model=OrderResponse)
async def update_item(
    order_id: UUID,
    item_id: UUID,
    body: OrderItemUpdateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> OrderResponse:
    try:
        order, items = await OrderService(session).update_item(
            context, order_id, item_id, body.quantity
        )
    except (OrderNotFoundError, OrderConflictError, TenantAccessDeniedError) as exc:
        raise translate(exc) from exc
    return response(order, items)


@router.delete("/{order_id}/items/{item_id}", status_code=204)
async def remove_item(
    order_id: UUID,
    item_id: UUID,
    session: SessionDependency,
    context: TenantContextDependency,
) -> Response:
    try:
        await OrderService(session).remove_item(context, order_id, item_id)
    except (OrderNotFoundError, OrderConflictError, TenantAccessDeniedError) as exc:
        raise translate(exc) from exc
    return Response(status_code=204)


@router.post("/{order_id}/confirm", response_model=OrderResponse)
async def confirm_order(
    order_id: UUID, session: SessionDependency, context: TenantContextDependency
) -> OrderResponse:
    try:
        order, items = await OrderService(session).confirm(context, order_id)
    except (
        OrderNotFoundError,
        OrderConflictError,
        OrderInsufficientStockError,
        TenantAccessDeniedError,
    ) as exc:
        raise translate(exc) from exc
    return response(order, items)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: UUID, session: SessionDependency, context: TenantContextDependency
) -> OrderResponse:
    try:
        order, items = await OrderService(session).cancel(context, order_id)
    except (OrderNotFoundError, OrderConflictError, TenantAccessDeniedError) as exc:
        raise translate(exc) from exc
    return response(order, items)
