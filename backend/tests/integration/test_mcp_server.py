"""MCP protocol, authentication, schemas, tenant scope, audit, and evaluation tests."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select, update

from nexus.bootstrap.config import Settings
from nexus.mcp.server import create_mcp_server
from nexus.modules.business_agent.models import AgentRun, AgentToolInvocation
from nexus.modules.inventory.models import StockLevel
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_analytics_api import complete_payment
from tests.integration.test_catalog_api import invite_and_accept
from tests.integration.test_payments_api import auth, register

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
pytest_plugins = ("tests.integration.test_payments_api",)


def mcp_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }
    if token is not None:
        headers.update(auth(token))
    return headers


async def mcp_rpc(
    client: AsyncClient,
    method: str,
    params: dict[str, object],
    *,
    token: str | None,
    request_id: int = 1,
) -> Response:
    return await client.post(
        "/mcp",
        headers=mcp_headers(token),
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
    )


@pytest.fixture
async def mcp_client(payment_database_url: str) -> AsyncIterator[tuple[AsyncClient, Settings]]:
    settings = Settings(
        environment="test",
        database_url=payment_database_url,
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        payment_webhook_secret="task15-test-webhook-secret-at-least-32-characters",
        mcp_issuer_url="http://test",
        mcp_server_url="http://test/mcp",
        _env_file=None,
    )
    manager = DatabaseManager(payment_database_url, 5)
    server = create_mcp_server(settings, manager)
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        max_request_body_size=64 * 1024,
        host="test",
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, settings


async def test_mcp_requires_authentication_and_rejects_malformed_input(
    mcp_client: tuple[AsyncClient, Settings], payment_client: AsyncClient
) -> None:
    client, _ = mcp_client
    unauthorized = await mcp_rpc(client, "tools/list", {}, token=None)
    assert unauthorized.status_code == 401

    token = await register(payment_client, "mcp-malformed@example.com")
    malformed = await mcp_rpc(
        client,
        "tools/call",
        {
            "name": "get_revenue_summary",
            "arguments": {"date_from": "not-a-date", "date_to": "2026-10-31"},
        },
        token=token,
    )
    assert malformed.status_code == 200
    body = malformed.json()
    assert body["result"]["isError"] is True
    assert "validation" in body["result"]["content"][0]["text"].lower()

    owner_token = await register(payment_client, "mcp-acl-owner@example.com")
    viewer_token = await register(payment_client, "mcp-acl-viewer@example.com")
    owner_setup, _ = await complete_payment(payment_client, owner_token, "mcp-acl-owner")
    await invite_and_accept(
        payment_client,
        owner_token,
        viewer_token,
        str(owner_setup["organization_id"]),
        "mcp-acl-viewer@example.com",
        "viewer",
    )
    today = datetime.now(UTC).date().isoformat()
    denied = await mcp_rpc(
        client,
        "tools/call",
        {
            "name": "get_revenue_summary",
            "arguments": {"date_from": today, "date_to": today, "currency": "USD"},
        },
        token=viewer_token,
    )
    assert denied.status_code == 200
    assert denied.json()["result"]["isError"] is True


async def test_mcp_tool_allowlist_correctness_tenant_scope_and_audit(
    mcp_client: tuple[AsyncClient, Settings],
    payment_client: AsyncClient,
    payment_database_url: str,
) -> None:
    client, _ = mcp_client
    token = await register(payment_client, "mcp-owner@example.com")
    setup, _ = await complete_payment(payment_client, token, "mcp-owner")
    organization_id = UUID(str(setup["organization_id"]))
    manager = DatabaseManager(payment_database_url, 2)
    async with manager.transaction() as session:
        await session.execute(
            update(StockLevel)
            .where(StockLevel.organization_id == organization_id)
            .values(low_stock_threshold=100)
        )

    listed = await mcp_rpc(client, "tools/list", {}, token=token)
    assert listed.status_code == 200, listed.text
    tools = listed.json()["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == {
        "get_revenue_summary",
        "get_top_products",
        "get_inventory_alerts",
        "compare_sales_periods",
    }
    assert all("inputSchema" in tool and "outputSchema" in tool for tool in tools)

    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    calls: dict[str, dict[str, object]] = {
        "get_revenue_summary": {
            "date_from": today.isoformat(),
            "date_to": today.isoformat(),
            "currency": "USD",
        },
        "get_top_products": {
            "date_from": today.isoformat(),
            "date_to": today.isoformat(),
            "currency": "USD",
            "limit": 5,
        },
        "get_inventory_alerts": {"limit": 20},
        "compare_sales_periods": {
            "period_a_from": yesterday.isoformat(),
            "period_a_to": yesterday.isoformat(),
            "period_b_from": today.isoformat(),
            "period_b_to": today.isoformat(),
            "currency": "USD",
        },
    }
    results: dict[str, dict[str, Any]] = {}
    for index, (name, arguments) in enumerate(calls.items(), start=10):
        response = await mcp_rpc(
            client,
            "tools/call",
            {"name": name, "arguments": arguments},
            token=token,
            request_id=index,
        )
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["isError"] is False, result
        results[name] = result["structuredContent"]

    assert results["get_revenue_summary"]["total_revenue"] == "20.0000"
    assert results["get_top_products"]["products"][0]["name"] == "Product mcp-owner"
    assert results["get_inventory_alerts"]["alerts"][0]["product_name"] == "Product mcp-owner"
    assert results["compare_sales_periods"]["period_a"]["total_revenue"] == "0.0000"
    assert results["compare_sales_periods"]["period_b"]["total_revenue"] == "20.0000"

    evaluation = json.loads(
        (Path(__file__).parents[1] / "evaluation" / "mcp_ai_evaluation.json").read_text(
            encoding="utf-8"
        )
    )
    assert {case["tool"] for case in evaluation["tool_cases"]} == set(results)
    correct = sum(
        all(field in results[case["tool"]] for field in case["expected_fields"])
        for case in evaluation["tool_cases"]
    )
    assert correct / len(evaluation["tool_cases"]) == 1.0

    async with manager.transaction() as session:
        run_count = await session.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(
                AgentRun.organization_id == organization_id,
                AgentRun.correlation_id.is_not(None),
            )
        )
        audit_count = await session.scalar(
            select(func.count())
            .select_from(AgentToolInvocation)
            .where(AgentToolInvocation.organization_id == organization_id)
        )
    await manager.dispose()
    assert run_count == audit_count == 4


async def test_mcp_cannot_read_another_active_tenant(
    mcp_client: tuple[AsyncClient, Settings], payment_client: AsyncClient
) -> None:
    client, _ = mcp_client
    token_a = await register(payment_client, "mcp-tenant-a@example.com")
    await complete_payment(payment_client, token_a, "mcp-tenant-a-first")
    await complete_payment(payment_client, token_a, "mcp-tenant-a-second")
    token_b = await register(payment_client, "mcp-tenant-b@example.com")
    await complete_payment(payment_client, token_b, "mcp-tenant-b")
    today = datetime.now(UTC).date().isoformat()
    response = await mcp_rpc(
        client,
        "tools/call",
        {
            "name": "get_revenue_summary",
            "arguments": {"date_from": today, "date_to": today, "currency": "USD"},
        },
        token=token_b,
    )
    result = response.json()["result"]["structuredContent"]
    assert result["total_revenue"] == "20.0000"
    assert result["order_count"] == 1


async def test_mcp_tool_timeout_is_bounded_and_audited(
    mcp_client: tuple[AsyncClient, Settings],
    payment_client: AsyncClient,
    payment_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import BaseModel

    from nexus.modules.business_agent.tools import BusinessTools

    client, settings = mcp_client
    token = await register(payment_client, "mcp-timeout@example.com")
    setup, _ = await complete_payment(payment_client, token, "mcp-timeout")
    organization_id = UUID(str(setup["organization_id"]))

    async def slow_revenue(self: BusinessTools, value: BaseModel) -> dict[str, object]:
        del self, value
        await asyncio.sleep(0.05)
        return {}

    monkeypatch.setattr(BusinessTools, "_revenue", slow_revenue)
    settings.agent_tool_timeout_seconds = 0.001
    today = datetime.now(UTC).date().isoformat()
    response = await mcp_rpc(
        client,
        "tools/call",
        {
            "name": "get_revenue_summary",
            "arguments": {"date_from": today, "date_to": today, "currency": "USD"},
        },
        token=token,
    )
    assert response.status_code == 200
    assert response.json()["result"]["isError"] is True
    manager = DatabaseManager(payment_database_url, 2)
    async with manager.transaction() as session:
        invocation = await session.scalar(
            select(AgentToolInvocation)
            .where(AgentToolInvocation.organization_id == organization_id)
            .order_by(AgentToolInvocation.created_at.desc())
        )
        run = await session.scalar(
            select(AgentRun)
            .where(AgentRun.organization_id == organization_id)
            .order_by(AgentRun.created_at.desc())
        )
    await manager.dispose()
    assert invocation is not None
    assert invocation.status == "failed"
    assert invocation.error_code == "tool_timeout"
    assert run is not None
    assert run.status == "failed"
