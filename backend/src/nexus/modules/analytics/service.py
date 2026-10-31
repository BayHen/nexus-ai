"""Optimized PostgreSQL analytics queries scoped to one tenant."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import CTE

from nexus.modules.catalog.models import Product
from nexus.modules.inventory.models import StockLevel
from nexus.modules.orders.models import Order, OrderItem
from nexus.modules.organizations.models import Branch
from nexus.modules.payments.models import PaymentIntent, PaymentRefund

ZERO = Decimal("0.0000")
MONEY_QUANTUM = Decimal("0.0001")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM)


def date_bounds(
    date_from: date | None, date_to: date | None
) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(date_from, time.min, tzinfo=UTC) if date_from else None
    end = (
        datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
        if date_to
        else None
    )
    return start, end


class AnalyticsService:
    """Read-only analytics over completed and successfully paid orders."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _recognized_orders(
        self,
        organization_id: UUID,
        currency: str,
        date_from: date | None,
        date_to: date | None,
    ) -> CTE:
        refund_totals = (
            select(
                PaymentRefund.payment_id.label("payment_id"),
                func.sum(PaymentRefund.amount).label("refunded_amount"),
            )
            .where(
                PaymentRefund.organization_id == organization_id,
                PaymentRefund.status == "succeeded",
            )
            .group_by(PaymentRefund.payment_id)
            .cte("refund_totals")
        )
        start, end = date_bounds(date_from, date_to)
        conditions = [
            PaymentIntent.organization_id == organization_id,
            PaymentIntent.currency == currency,
            PaymentIntent.status.in_(("succeeded", "refunded")),
            PaymentIntent.succeeded_at.is_not(None),
            Order.organization_id == organization_id,
            Order.status == "completed",
        ]
        if start is not None:
            conditions.append(PaymentIntent.succeeded_at >= start)
        if end is not None:
            conditions.append(PaymentIntent.succeeded_at < end)
        refunded = func.coalesce(refund_totals.c.refunded_amount, ZERO)
        return (
            select(
                PaymentIntent.id.label("payment_id"),
                PaymentIntent.order_id.label("order_id"),
                PaymentIntent.succeeded_at.label("recognized_at"),
                PaymentIntent.amount.label("gross_amount"),
                refunded.label("refunded_amount"),
                (PaymentIntent.amount - refunded).label("net_amount"),
            )
            .join(
                Order,
                and_(
                    Order.organization_id == PaymentIntent.organization_id,
                    Order.id == PaymentIntent.order_id,
                ),
            )
            .outerjoin(refund_totals, refund_totals.c.payment_id == PaymentIntent.id)
            .where(*conditions)
            .cte("recognized_orders")
        )

    async def summary(
        self,
        organization_id: UUID,
        currency: str,
        date_from: date | None,
        date_to: date | None,
    ) -> dict[str, object]:
        recognized = self._recognized_orders(
            organization_id, currency, date_from, date_to
        )
        row = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(recognized.c.net_amount), ZERO),
                    func.coalesce(func.sum(recognized.c.gross_amount), ZERO),
                    func.coalesce(func.sum(recognized.c.refunded_amount), ZERO),
                    func.count(recognized.c.order_id),
                )
            )
        ).one()
        total, gross, refunded, count = cast(
            tuple[Decimal, Decimal, Decimal, int], row
        )
        order_count = int(count)
        average = money(total / order_count) if order_count else ZERO
        return {
            "currency": currency,
            "total_revenue": money(total),
            "gross_revenue": money(gross),
            "refunded_amount": money(refunded),
            "order_count": order_count,
            "average_order_value": average,
        }

    async def revenue_series(
        self,
        organization_id: UUID,
        currency: str,
        date_from: date | None,
        date_to: date | None,
        granularity: Literal["day", "month"],
    ) -> list[dict[str, object]]:
        recognized = self._recognized_orders(
            organization_id, currency, date_from, date_to
        )
        period = func.date_trunc(granularity, recognized.c.recognized_at).label("period")
        rows = (
            await self._session.execute(
                select(
                    period,
                    func.sum(recognized.c.net_amount).label("revenue"),
                    func.count(recognized.c.order_id).label("order_count"),
                )
                .group_by(period)
                .order_by(period)
            )
        ).all()
        return [
            {
                "period": row.period.date(),
                "revenue": money(Decimal(row.revenue)),
                "order_count": int(row.order_count),
            }
            for row in rows
        ]

    async def best_selling_products(
        self,
        organization_id: UUID,
        currency: str,
        date_from: date | None,
        date_to: date | None,
        limit: int,
    ) -> list[dict[str, object]]:
        recognized = self._recognized_orders(
            organization_id, currency, date_from, date_to
        )
        rows = (
            await self._session.execute(
                select(
                    OrderItem.product_id,
                    OrderItem.product_sku_snapshot,
                    OrderItem.product_name_snapshot,
                    func.sum(OrderItem.quantity).label("quantity_sold"),
                    func.sum(OrderItem.line_total).label("gross_sales"),
                )
                .join(
                    recognized,
                    and_(
                        recognized.c.order_id == OrderItem.order_id,
                        OrderItem.organization_id == organization_id,
                    ),
                )
                .group_by(
                    OrderItem.product_id,
                    OrderItem.product_sku_snapshot,
                    OrderItem.product_name_snapshot,
                )
                .order_by(func.sum(OrderItem.quantity).desc(), OrderItem.product_id)
                .limit(limit)
            )
        ).all()
        return [
            {
                "product_id": row.product_id,
                "sku": row.product_sku_snapshot,
                "name": row.product_name_snapshot,
                "quantity_sold": Decimal(row.quantity_sold),
                "gross_sales": money(Decimal(row.gross_sales)),
            }
            for row in rows
        ]

    async def inventory_valuation(
        self, organization_id: UUID, currency: str
    ) -> dict[str, object]:
        rows = (
            await self._session.execute(
                select(
                    StockLevel.branch_id,
                    func.sum(StockLevel.quantity * Product.price).label("valuation"),
                )
                .join(
                    Product,
                    and_(
                        Product.organization_id == StockLevel.organization_id,
                        Product.id == StockLevel.product_id,
                    ),
                )
                .where(StockLevel.organization_id == organization_id)
                .group_by(StockLevel.branch_id)
                .order_by(StockLevel.branch_id)
            )
        ).all()
        branches = [
            {"branch_id": row.branch_id, "valuation": money(Decimal(row.valuation))}
            for row in rows
        ]
        return {
            "currency": currency,
            "policy": "current_retail_price",
            "total_valuation": money(
                sum((item["valuation"] for item in branches), start=ZERO)
            ),
            "branches": branches,
        }

    async def branch_revenue(
        self,
        organization_id: UUID,
        currency: str,
        date_from: date | None,
        date_to: date | None,
    ) -> list[dict[str, object]]:
        recognized = self._recognized_orders(
            organization_id, currency, date_from, date_to
        )
        allocation = recognized.c.net_amount / recognized.c.gross_amount
        rows = (
            await self._session.execute(
                select(
                    OrderItem.branch_id,
                    Branch.name.label("branch_name"),
                    func.sum(OrderItem.line_total * allocation).label("net_revenue"),
                )
                .join(
                    recognized,
                    and_(
                        recognized.c.order_id == OrderItem.order_id,
                        OrderItem.organization_id == organization_id,
                    ),
                )
                .join(
                    Branch,
                    and_(
                        Branch.organization_id == OrderItem.organization_id,
                        Branch.id == OrderItem.branch_id,
                    ),
                )
                .group_by(OrderItem.branch_id, Branch.name)
                .order_by(func.sum(OrderItem.line_total * allocation).desc(), OrderItem.branch_id)
            )
        ).all()
        return [
            {
                "branch_id": row.branch_id,
                "branch_name": row.branch_name,
                "net_revenue": money(Decimal(row.net_revenue)),
            }
            for row in rows
        ]
