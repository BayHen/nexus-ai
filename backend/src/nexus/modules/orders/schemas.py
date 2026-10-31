"""Order API request and response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreateRequest(BaseModel):
    product_id: UUID
    branch_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=19, decimal_places=4)


class OrderItemUpdateRequest(BaseModel):
    quantity: Decimal = Field(gt=0, max_digits=19, decimal_places=4)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    branch_id: UUID
    product_sku_snapshot: str
    product_name_snapshot: str
    unit_price_snapshot: Decimal
    quantity: Decimal
    line_total: Decimal


class OrderResponse(BaseModel):
    id: UUID
    status: Literal["draft", "confirmed", "completed", "cancelled"]
    total_amount: Decimal
    items: list[OrderItemResponse]
    created_by_user_id: UUID | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrderPageResponse(BaseModel):
    items: list[OrderResponse]
    page: int
    page_size: int
    total: int
