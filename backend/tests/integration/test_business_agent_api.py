"""LangGraph tool selection, correctness, audit, timeout, and tenant security tests."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient, Response
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from nexus.modules.business_agent.models import AgentRun, AgentToolInvocation
from nexus.modules.business_agent.tools import BusinessTools
from nexus.modules.inventory.models import StockLevel
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_analytics_api import complete_payment
from tests.integration.test_catalog_api import invite_and_accept
from tests.integration.test_payments_api import (
    auth,
    create_intent,
    register,
    send_webhook,
    setup_confirmed_order,
    signed_payment_event,
)

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
pytest_plugins = ("tests.integration.test_payments_api",)


async def ask(client: AsyncClient, token: str, question: str, **extra: Any) -> Response:
    return await client.post(
        "/api/v1/agent/ask",
        headers=auth(token),
        json={"question": question, **extra},
    )


async def test_supported_tools_factual_answers_citations_and_audit(
    payment_client: AsyncClient, payment_database_url: str
) -> None:
    token = await register(payment_client, "agent-owner@example.com")
    setup, _ = await complete_payment(payment_client, token, "agent-owner")
    organization_id = UUID(str(setup["organization_id"]))
    manager = DatabaseManager(payment_database_url, 2)
    async with manager.transaction() as session:
        await session.execute(
            update(StockLevel)
            .where(StockLevel.organization_id == organization_id)
            .values(low_stock_threshold=100)
        )
    uploaded = await payment_client.post(
        "/api/v1/knowledge/documents",
        headers=auth(token),
        data={"visibility": "organization"},
        files={
            "file": (
                "agent-policy.md",
                b"Business policy code ORANGE requires manager approval.",
                "text/markdown",
            )
        },
    )
    assert uploaded.status_code == 201

    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    requests = {
        "get_revenue_summary": ("What was our revenue this month?", {}),
        "get_top_products": ("Which products sold the most?", {}),
        "get_inventory_alerts": ("Which products are running low?", {}),
        "compare_sales_periods": (
            "Compare sales between two selected periods.",
            {
                "period_a": {"date_from": yesterday.isoformat(), "date_to": yesterday.isoformat()},
                "period_b": {"date_from": today.isoformat(), "date_to": today.isoformat()},
            },
        ),
        "search_knowledge_base": (
            "Summarize document: Business policy code ORANGE requires manager approval.",
            {},
        ),
    }
    responses = {}
    for expected_tool, (question, payload) in requests.items():
        response = await ask(payment_client, token, question, **payload)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed", {"expected_tool": expected_tool, "body": body}
        assert body["selected_tool"] == expected_tool
        assert body["transitions"] == ["authorize", "plan", "execute_tool", "compose_answer"]
        responses[expected_tool] = body

    assert "20.0000 USD" in responses["get_revenue_summary"]["answer"]
    assert "Product agent-owner" in responses["get_top_products"]["answer"]
    assert "Low-stock products" in responses["get_inventory_alerts"]["answer"]
    assert "difference B-A was 20.0000" in responses["compare_sales_periods"]["answer"]
    knowledge = responses["search_knowledge_base"]
    assert "ORANGE" in knowledge["answer"]
    assert knowledge["citations"][0]["document_id"] == uploaded.json()["id"]

    dataset = json.loads(
        (Path(__file__).parents[1] / "evaluation" / "business_agent_tools.json").read_text(
            encoding="utf-8"
        )
    )
    assert {item["expected_tool"] for item in dataset} == set(requests)
    async with manager.transaction() as session:
        runs = await session.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(
                AgentRun.organization_id == organization_id,
                AgentRun.status == "completed",
            )
        )
        invocations = list(
            await session.scalars(
                select(AgentToolInvocation).where(
                    AgentToolInvocation.organization_id == organization_id
                )
            )
        )
        assert runs == 5
        assert len(invocations) == 5
        knowledge_audit = next(
            item for item in invocations if item.tool_name == "search_knowledge_base"
        )
        assert "query" not in knowledge_audit.input_metadata
        assert int(str(knowledge_audit.input_metadata["query_length"])) > 0
        assert len(str(knowledge_audit.input_metadata["query_sha256"])) == 64
    with pytest.raises(DBAPIError, match="reliability history is immutable"):
        async with manager.transaction() as session:
            await session.execute(
                update(AgentToolInvocation)
                .where(AgentToolInvocation.organization_id == organization_id)
                .values(status="tampered")
            )
    await manager.dispose()


async def test_tool_authorization_write_boundary_and_tenant_isolation(
    payment_client: AsyncClient,
) -> None:
    owner_token = await register(payment_client, "agent-acl-owner@example.com")
    viewer_token = await register(payment_client, "agent-acl-viewer@example.com")
    owner_setup, _ = await complete_payment(payment_client, owner_token, "agent-acl-owner")
    await invite_and_accept(
        payment_client,
        owner_token,
        viewer_token,
        str(owner_setup["organization_id"]),
        "agent-acl-viewer@example.com",
        "viewer",
    )
    denied = await ask(payment_client, viewer_token, "What was our revenue this month?")
    assert denied.status_code == 200
    assert denied.json()["status"] == "denied"
    assert denied.json()["selected_tool"] == "get_revenue_summary"

    write = await ask(payment_client, owner_token, "Delete all products now")
    assert write.json()["status"] == "unsupported"
    assert write.json()["selected_tool"] is None
    assert "explicit user confirmation" in write.json()["answer"]

    outsider_token = await register(payment_client, "agent-outsider@example.com")
    outsider_setup = await setup_confirmed_order(
        payment_client, outsider_token, "agent-outsider", price="7.0000"
    )
    outsider_intent = await create_intent(
        payment_client, outsider_token, outsider_setup["order_id"], "agent-outsider-intent"
    )
    raw, signature = signed_payment_event(outsider_intent.json()["provider_intent_id"], "succeeded")
    assert (await send_webhook(payment_client, raw, signature)).status_code == 200
    assert outsider_setup["organization_id"] != owner_setup["organization_id"]
    outsider = await ask(payment_client, outsider_token, "What was our revenue this month?")
    assert "14.0000 USD" in outsider.json()["answer"]
    assert "20.0000" not in outsider.json()["answer"]


async def test_tool_timeout_reaches_failed_terminal_state(
    payment_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await register(payment_client, "agent-timeout@example.com")
    await complete_payment(payment_client, token, "agent-timeout")

    async def slow_revenue(self: BusinessTools, value: BaseModel) -> dict[str, object]:
        del self, value
        await asyncio.sleep(0.05)
        return {}

    monkeypatch.setattr(BusinessTools, "_revenue", slow_revenue)
    app = payment_client._transport.app  # type: ignore[attr-defined]
    original_timeout = app.state.settings.agent_tool_timeout_seconds
    app.state.settings.agent_tool_timeout_seconds = 0.001
    try:
        response = await ask(payment_client, token, "What was our revenue this month?")
    finally:
        app.state.settings.agent_tool_timeout_seconds = original_timeout
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["transitions"] == [
        "authorize",
        "plan",
        "execute_tool",
        "compose_answer",
    ]
