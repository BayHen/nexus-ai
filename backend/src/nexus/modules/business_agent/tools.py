"""Typed, read-only, authorized business intelligence tools."""

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from datetime import date
from time import perf_counter
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.analytics.service import AnalyticsService
from nexus.modules.business_agent.models import AgentToolInvocation
from nexus.modules.catalog.models import Product
from nexus.modules.inventory.models import StockLevel
from nexus.modules.knowledge.service import KnowledgeService
from nexus.modules.organizations.domain import Permission, TenantContext, has_permission
from nexus.modules.organizations.models import Branch


class RevenueSummaryInput(BaseModel):
    date_from: date
    date_to: date
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def validate_range(self) -> "RevenueSummaryInput":
        if self.date_from > self.date_to:
            raise ValueError("date_from cannot be later than date_to")
        return self


class TopProductsInput(RevenueSummaryInput):
    limit: int = Field(default=5, ge=1, le=20)


class InventoryAlertsInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


class CompareSalesPeriodsInput(BaseModel):
    period_a_from: date
    period_a_to: date
    period_b_from: date
    period_b_to: date
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def validate_ranges(self) -> "CompareSalesPeriodsInput":
        if self.period_a_from > self.period_a_to or self.period_b_from > self.period_b_to:
            raise ValueError("comparison period start cannot be later than end")
        return self


class KnowledgeSearchInput(BaseModel):
    query: str = Field(min_length=3, max_length=2000)


class ToolAuthorizationError(PermissionError):
    pass


class BusinessTools:
    """Tool registry with fixed SQL/application calls and no arbitrary query surface."""

    def __init__(
        self,
        session: AsyncSession,
        context: TenantContext,
        knowledge: KnowledgeService,
        *,
        run_id: UUID,
        correlation_id: str | None,
        timeout_seconds: float,
        retrieval_limit: int,
        distance_threshold: float,
    ) -> None:
        self._session = session
        self._context = context
        self._knowledge = knowledge
        self._run_id = run_id
        self._correlation_id = correlation_id
        self._timeout_seconds = timeout_seconds
        self._retrieval_limit = retrieval_limit
        self._distance_threshold = distance_threshold

    async def invoke(self, name: str, raw_input: dict[str, object]) -> dict[str, object]:
        handlers: dict[
            str,
            tuple[
                type[BaseModel],
                Callable[[BaseModel], Awaitable[dict[str, object]]],
                Permission,
            ],
        ] = {
            "get_revenue_summary": (RevenueSummaryInput, self._revenue, Permission.AUDIT_READ),
            "get_top_products": (TopProductsInput, self._top_products, Permission.AUDIT_READ),
            "get_inventory_alerts": (
                InventoryAlertsInput,
                self._inventory_alerts,
                Permission.INVENTORY_READ,
            ),
            "compare_sales_periods": (
                CompareSalesPeriodsInput,
                self._compare_sales,
                Permission.AUDIT_READ,
            ),
            "search_knowledge_base": (
                KnowledgeSearchInput,
                self._search_knowledge,
                Permission.KNOWLEDGE_READ,
            ),
        }
        if name not in handlers:
            raise ValueError("unsupported_tool")
        schema, handler, permission = handlers[name]
        if not has_permission(self._context.role, permission):
            await self._audit(name, "denied", raw_input, {}, "tool_access_denied", 0)
            raise ToolAuthorizationError("tool_access_denied")
        typed_input = schema.model_validate(raw_input)
        started = perf_counter()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                result = await handler(typed_input)
        except TimeoutError:
            duration = int((perf_counter() - started) * 1000)
            await self._audit(name, "failed", raw_input, {}, "tool_timeout", duration)
            raise
        except Exception as exc:
            duration = int((perf_counter() - started) * 1000)
            await self._audit(name, "failed", raw_input, {}, type(exc).__name__, duration)
            raise
        duration = int((perf_counter() - started) * 1000)
        await self._audit(name, "succeeded", raw_input, result, None, duration)
        return result

    async def _revenue(self, value: BaseModel) -> dict[str, object]:
        item = RevenueSummaryInput.model_validate(value)
        return await AnalyticsService(self._session).summary(
            self._context.organization_id,
            item.currency,
            item.date_from,
            item.date_to,
        )

    async def _top_products(self, value: BaseModel) -> dict[str, object]:
        item = TopProductsInput.model_validate(value)
        products = await AnalyticsService(self._session).best_selling_products(
            self._context.organization_id,
            item.currency,
            item.date_from,
            item.date_to,
            item.limit,
        )
        return {"currency": item.currency, "products": products}

    async def _inventory_alerts(self, value: BaseModel) -> dict[str, object]:
        item = InventoryAlertsInput.model_validate(value)
        rows = (
            await self._session.execute(
                select(StockLevel, Product.name, Product.sku, Branch.name.label("branch_name"))
                .join(
                    Product,
                    and_(
                        Product.organization_id == StockLevel.organization_id,
                        Product.id == StockLevel.product_id,
                    ),
                )
                .join(
                    Branch,
                    and_(
                        Branch.organization_id == StockLevel.organization_id,
                        Branch.id == StockLevel.branch_id,
                    ),
                )
                .where(
                    StockLevel.organization_id == self._context.organization_id,
                    StockLevel.quantity <= StockLevel.low_stock_threshold,
                )
                .order_by(StockLevel.quantity, Product.id)
                .limit(item.limit)
            )
        ).all()
        return {
            "alerts": [
                {
                    "product_id": str(stock.product_id),
                    "product_name": product_name,
                    "sku": sku,
                    "branch_id": str(stock.branch_id),
                    "branch_name": branch_name,
                    "quantity": str(stock.quantity),
                    "threshold": str(stock.low_stock_threshold),
                }
                for stock, product_name, sku, branch_name in rows
            ]
        }

    async def _compare_sales(self, value: BaseModel) -> dict[str, object]:
        item = CompareSalesPeriodsInput.model_validate(value)
        analytics = AnalyticsService(self._session)
        first = await analytics.summary(
            self._context.organization_id,
            item.currency,
            item.period_a_from,
            item.period_a_to,
        )
        second = await analytics.summary(
            self._context.organization_id,
            item.currency,
            item.period_b_from,
            item.period_b_to,
        )
        return {"period_a": first, "period_b": second, "currency": item.currency}

    async def _search_knowledge(self, value: BaseModel) -> dict[str, object]:
        item = KnowledgeSearchInput.model_validate(value)
        answer, evidence, supported = await self._knowledge.answer(
            organization_id=self._context.organization_id,
            user_id=self._context.user_id,
            role=self._context.role,
            question=item.query,
            limit=self._retrieval_limit,
            distance_threshold=self._distance_threshold,
        )
        return {
            "answer": answer,
            "supported": supported,
            "citations": [
                {
                    "document_id": evidence_item.document_id,
                    "document_name": evidence_item.document_name,
                    "chunk_ordinal": evidence_item.chunk_ordinal,
                    "excerpt": evidence_item.content[:240],
                    "distance": evidence_item.distance,
                }
                for evidence_item in evidence
            ],
        }

    async def _audit(
        self,
        tool_name: str,
        status: str,
        raw_input: dict[str, object],
        output: dict[str, object],
        error_code: str | None,
        duration_ms: int,
    ) -> None:
        input_metadata: dict[str, object] = {
            key: value for key, value in raw_input.items() if key != "query"
        }
        if "query" in raw_input:
            query = str(raw_input["query"])
            input_metadata["query_length"] = len(query)
            input_metadata["query_sha256"] = hashlib.sha256(query.encode()).hexdigest()
        items = output.get("alerts", output.get("products", []))
        output_metadata = {
            "item_count": len(items) if isinstance(items, list) else 0,
            "supported": output.get("supported") if "supported" in output else None,
        }
        self._session.add(
            AgentToolInvocation(
                organization_id=self._context.organization_id,
                user_id=self._context.user_id,
                run_id=self._run_id,
                tool_name=tool_name,
                status=status,
                input_metadata=input_metadata,
                output_metadata=output_metadata,
                error_code=error_code,
                duration_ms=duration_ms,
                correlation_id=self._correlation_id,
            )
        )
        await self._session.flush()
