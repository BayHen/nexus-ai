"""Catalog HTTP transport schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

CategoryName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)
]
ProductName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Slug = Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
Description = Annotated[str, Field(max_length=4000)]
Money = Annotated[Decimal, Field(ge=0, max_digits=19, decimal_places=4)]
ProductStatus = Literal["draft", "active", "archived"]


class CategoryCreateRequest(BaseModel):
    name: CategoryName
    slug: Slug
    description: Description | None = None


class CategoryUpdateRequest(BaseModel):
    name: CategoryName | None = None
    slug: Slug | None = None
    description: Description | None = None

    @model_validator(mode="after")
    def require_change(self) -> "CategoryUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one category field must be provided")
        return self


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class CategoryPageResponse(BaseModel):
    items: list[CategoryResponse]
    page: int
    page_size: int
    total: int


class ProductCreateRequest(BaseModel):
    name: ProductName
    description: Description | None = None
    price: Money
    status: ProductStatus = "draft"
    category_id: UUID | None = None


class ProductUpdateRequest(BaseModel):
    name: ProductName | None = None
    description: Description | None = None
    price: Money | None = None
    status: ProductStatus | None = None
    category_id: UUID | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ProductUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one product field must be provided")
        return self


class ProductResponse(BaseModel):
    id: UUID
    category_id: UUID | None
    sku: str
    name: str
    description: str | None
    price: Decimal
    status: ProductStatus
    created_at: datetime
    updated_at: datetime


class ProductPageResponse(BaseModel):
    items: list[ProductResponse]
    page: int
    page_size: int
    total: int
