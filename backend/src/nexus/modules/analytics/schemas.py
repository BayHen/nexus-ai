"""Transport schemas for analytics APIs."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyticsSummaryResponse(BaseModel):
    currency: str
    total_revenue: Decimal
    gross_revenue: Decimal
    refunded_amount: Decimal
    order_count: int
    average_order_value: Decimal


class RevenuePeriodItem(BaseModel):
    period: date
    revenue: Decimal
    order_count: int


class RevenueSeriesResponse(BaseModel):
    currency: str
    granularity: Literal["day", "month"]
    items: list[RevenuePeriodItem]


class BestSellingProductItem(BaseModel):
    product_id: UUID
    sku: str
    name: str
    quantity_sold: Decimal
    gross_sales: Decimal


class BestSellingProductsResponse(BaseModel):
    currency: str
    items: list[BestSellingProductItem]


class InventoryValuationItem(BaseModel):
    branch_id: UUID
    valuation: Decimal


class InventoryValuationResponse(BaseModel):
    currency: str
    policy: Literal["current_retail_price"] = "current_retail_price"
    total_valuation: Decimal
    branches: list[InventoryValuationItem]


class BranchRevenueItem(BaseModel):
    branch_id: UUID
    branch_name: str
    net_revenue: Decimal


class BranchRevenueResponse(BaseModel):
    currency: str
    items: list[BranchRevenueItem]


class AnalyticsExportRequest(BaseModel):
    file_format: Literal["csv", "xlsx"]
    date_from: date | None = None
    date_to: date | None = None
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class AnalyticsExportResponse(BaseModel):
    job_id: UUID
    status: Literal["queued", "running", "retrying", "succeeded", "failed", "dead"]
    created: bool
