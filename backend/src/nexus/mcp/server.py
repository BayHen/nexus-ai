"""Authenticated, tenant-scoped MCP server for approved read-only analytics tools."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from pydantic import BaseModel, Field
from pydantic_core import to_jsonable_python

from nexus.bootstrap.config import Settings, get_settings
from nexus.modules.analytics.schemas import AnalyticsSummaryResponse
from nexus.modules.auth.domain import TokenInvalidError
from nexus.modules.auth.security import decode_access_token
from nexus.modules.business_agent.models import AgentRun
from nexus.modules.business_agent.tools import BusinessTools, ToolAuthorizationError
from nexus.modules.knowledge.providers import DeterministicAIProvider
from nexus.modules.knowledge.service import KnowledgeService
from nexus.modules.organizations.domain import (
    Permission,
    TenantContextRequiredError,
    has_permission,
)
from nexus.modules.organizations.service import OrganizationService
from nexus.platform.database.manager import DatabaseManager, DatabaseUnavailableError
from nexus.platform.database.protocols import TransactionManagerProtocol

logger = logging.getLogger(__name__)


class TopProductOutput(BaseModel):
    product_id: UUID
    sku: str
    name: str
    quantity_sold: Decimal
    gross_sales: Decimal


class TopProductsOutput(BaseModel):
    currency: str
    products: list[TopProductOutput]


class InventoryAlertOutput(BaseModel):
    product_id: UUID
    product_name: str
    sku: str
    branch_id: UUID
    branch_name: str
    quantity: Decimal
    threshold: Decimal


class InventoryAlertsOutput(BaseModel):
    alerts: list[InventoryAlertOutput]


class SalesComparisonOutput(BaseModel):
    period_a: AnalyticsSummaryResponse
    period_b: AnalyticsSummaryResponse
    currency: str


class NexusTokenVerifier(TokenVerifier):
    """Validate existing NEXUS access JWTs for the dedicated MCP resource server."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = decode_access_token(token, self._settings)
            subject = str(claims["sub"])
        except (TokenInvalidError, KeyError, TypeError, ValueError):
            return None
        return AccessToken(
            token=token,
            client_id="nexus-first-party",
            scopes=["mcp:read"],
            expires_at=int(claims["exp"]),
            subject=subject,
            claims=claims,
        )


class McpBusinessToolAdapter:
    """Resolve identity and active tenant before invoking the shared tool registry."""

    def __init__(self, manager: TransactionManagerProtocol, settings: Settings) -> None:
        self._manager = manager
        self._settings = settings

    async def invoke(
        self,
        tool_name: str,
        arguments: dict[str, object],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        access_token = get_access_token()
        if access_token is None or access_token.claims is None:
            raise PermissionError("authentication_required")
        try:
            user_id = UUID(str(access_token.claims["sub"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise PermissionError("authentication_required") from exc

        correlation_id = str(uuid4())
        deferred_error: Exception | None = None
        validated: BaseModel | None = None
        async with self._manager.transaction() as session:
            try:
                tenant = await OrganizationService(session).resolve_tenant_context(user_id)
            except TenantContextRequiredError as exc:
                raise PermissionError("active_tenant_required") from exc
            run = AgentRun(
                organization_id=tenant.organization_id,
                user_id=user_id,
                status="running",
                selected_tool=tool_name,
                correlation_id=correlation_id,
            )
            session.add(run)
            await session.flush()
            if not has_permission(tenant.role, Permission.AI_ASSISTANT_USE):
                run.status = "denied"
                run.error_code = "mcp_access_denied"
                deferred_error = PermissionError("tool_access_denied")
            else:
                provider = DeterministicAIProvider()
                tools = BusinessTools(
                    session,
                    tenant,
                    KnowledgeService(session, provider, provider),
                    run_id=run.id,
                    correlation_id=correlation_id,
                    timeout_seconds=self._settings.agent_tool_timeout_seconds,
                    retrieval_limit=self._settings.knowledge_retrieval_limit,
                    distance_threshold=self._settings.knowledge_distance_threshold,
                )
                try:
                    safe_arguments = to_jsonable_python(arguments)
                    result = await tools.invoke(tool_name, safe_arguments)
                    validated = output_schema.model_validate(result)
                    run.status = "completed"
                except ToolAuthorizationError:
                    run.status = "denied"
                    run.error_code = "tool_access_denied"
                    deferred_error = PermissionError("tool_access_denied")
                except Exception as exc:
                    logger.warning(
                        "MCP tool execution failed",
                        extra={"event": "mcp_tool_failed", "error_type": type(exc).__name__},
                    )
                    run.status = "failed"
                    run.error_code = "tool_execution_failed"
                    deferred_error = RuntimeError("tool_execution_failed")
            run.transition_count = 1
            run.completed_at = datetime.now(UTC)
            await session.flush()
        if deferred_error is not None:
            raise deferred_error
        if validated is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("tool_execution_failed")
        return validated


def create_mcp_server(
    settings: Settings,
    manager: TransactionManagerProtocol,
) -> MCPServer[Any]:
    """Build a stateless MCP server with an explicit four-tool allowlist."""

    @asynccontextmanager
    async def lifespan(_: MCPServer[Any]) -> AsyncIterator[None]:
        if not await manager.check_connection():
            raise DatabaseUnavailableError("Database is unavailable during MCP startup")
        try:
            yield
        finally:
            await manager.dispose()

    server: MCPServer[Any] = MCPServer(
        name="nexus-business-intelligence",
        version=settings.app_version,
        instructions=(
            "Read-only tenant-scoped business analytics. Never infer tenant identifiers or "
            "attempt write operations."
        ),
        token_verifier=NexusTokenVerifier(settings),
        auth=AuthSettings(
            issuer_url=settings.mcp_issuer_url,
            resource_server_url=settings.mcp_server_url,
            required_scopes=["mcp:read"],
            validate_token_resource=False,
        ),
        lifespan=lifespan,
    )
    adapter = McpBusinessToolAdapter(manager, settings)

    @server.tool(description="Return recognized net revenue and order metrics for a date range.")
    async def get_revenue_summary(
        date_from: date,
        date_to: date,
        currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$"),
    ) -> AnalyticsSummaryResponse:
        return AnalyticsSummaryResponse.model_validate(
            await adapter.invoke(
                "get_revenue_summary",
                {"date_from": date_from, "date_to": date_to, "currency": currency},
                AnalyticsSummaryResponse,
            )
        )

    @server.tool(description="Return the best-selling products for a date range.")
    async def get_top_products(
        date_from: date,
        date_to: date,
        currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$"),
        limit: int = Field(default=5, ge=1, le=20),
    ) -> TopProductsOutput:
        return TopProductsOutput.model_validate(
            await adapter.invoke(
                "get_top_products",
                {
                    "date_from": date_from,
                    "date_to": date_to,
                    "currency": currency,
                    "limit": limit,
                },
                TopProductsOutput,
            )
        )

    @server.tool(description="Return products at or below the configured low-stock threshold.")
    async def get_inventory_alerts(
        limit: int = Field(default=20, ge=1, le=100),
    ) -> InventoryAlertsOutput:
        return InventoryAlertsOutput.model_validate(
            await adapter.invoke("get_inventory_alerts", {"limit": limit}, InventoryAlertsOutput)
        )

    @server.tool(description="Compare recognized sales metrics between two selected periods.")
    async def compare_sales_periods(
        period_a_from: date,
        period_a_to: date,
        period_b_from: date,
        period_b_to: date,
        currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$"),
    ) -> SalesComparisonOutput:
        return SalesComparisonOutput.model_validate(
            await adapter.invoke(
                "compare_sales_periods",
                {
                    "period_a_from": period_a_from,
                    "period_a_to": period_a_to,
                    "period_b_from": period_b_from,
                    "period_b_to": period_b_to,
                    "currency": currency,
                },
                SalesComparisonOutput,
            )
        )

    return server


def main() -> None:
    """Run the dedicated stateless Streamable HTTP MCP process."""
    settings = get_settings()
    manager = DatabaseManager(
        settings.database_url.get_secret_value(), settings.database_connect_timeout_seconds
    )
    create_mcp_server(settings, manager).run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
        stateless_http=True,
        json_response=True,
        max_request_body_size=64 * 1024,
    )
