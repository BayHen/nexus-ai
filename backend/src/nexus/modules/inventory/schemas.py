"""Inventory HTTP transport schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

Quantity = Annotated[Decimal, Field(max_digits=19, decimal_places=4)]
NonNegativeQuantity = Annotated[Decimal, Field(ge=0, max_digits=19, decimal_places=4)]


class StockCreateRequest(BaseModel):
    branch_id: UUID
    product_id: UUID
    low_stock_threshold: NonNegativeQuantity = Decimal("0")


class ThresholdUpdateRequest(BaseModel):
    low_stock_threshold: NonNegativeQuantity


class StockResponse(BaseModel):
    branch_id: UUID
    branch_name: str | None
    product_id: UUID
    product_name: str | None
    product_sku: str | None
    quantity: Decimal
    low_stock_threshold: Decimal
    is_low_stock: bool
    updated_at: datetime


class StockPageResponse(BaseModel):
    items: list[StockResponse]
    page: int
    page_size: int
    total: int


class AdjustmentRequest(BaseModel):
    branch_id: UUID
    product_id: UUID
    quantity_delta: Quantity
    reason: Annotated[str, Field(min_length=2, max_length=1000)]
    reference: Annotated[str, Field(min_length=1, max_length=160)] | None = None

    @model_validator(mode="after")
    def non_zero_quantity(self) -> "AdjustmentRequest":
        if self.quantity_delta == 0:
            raise ValueError("Adjustment quantity must be non-zero")
        return self


class TransferRequest(BaseModel):
    source_branch_id: UUID
    destination_branch_id: UUID
    product_id: UUID
    quantity: Annotated[Decimal, Field(gt=0, max_digits=19, decimal_places=4)]
    reason: Annotated[str, Field(min_length=2, max_length=1000)]
    reference: Annotated[str, Field(min_length=1, max_length=160)] | None = None


class MovementResponse(BaseModel):
    id: UUID
    movement_type: Literal["adjustment", "transfer"]
    product_id: UUID
    source_branch_id: UUID | None
    destination_branch_id: UUID | None
    quantity_delta: Decimal
    source_quantity_after: Decimal | None
    destination_quantity_after: Decimal | None
    reference: str | None
    reason: str
    actor_user_id: UUID | None
    created_at: datetime
    replayed: bool = False


class MovementPageResponse(BaseModel):
    items: list[MovementResponse]
    page: int
    page_size: int
    total: int


class InventoryPolicyUpdateRequest(BaseModel):
    allow_negative_stock: bool


class InventoryPolicyResponse(BaseModel):
    allow_negative_stock: bool
    updated_at: datetime
