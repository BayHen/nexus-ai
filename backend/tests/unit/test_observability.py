"""Behavioral tests for bounded and privacy-safe telemetry."""

import json
import logging

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import generate_latest

from nexus.platform.api.dependencies import ReadinessCheck, get_readiness_checks
from nexus.platform.database.manager import _bounded_operation
from nexus.platform.logging import JsonFormatter
from nexus.platform.observability.worker import registry, task_finished, task_started

pytestmark = pytest.mark.anyio


async def test_metrics_use_route_templates_and_exclude_raw_private_paths(
    client: AsyncClient,
) -> None:
    await client.get("/api/v1")
    await client.get("/private-customer-value/not-found")

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert 'route="/api/v1"' in response.text
    assert 'route="unmatched"' in response.text
    assert "private-customer-value" not in response.text


async def test_controlled_dependency_failure_updates_readiness_metric(
    app: FastAPI, client: AsyncClient
) -> None:
    async def unavailable() -> bool:
        return False

    def failing_checks() -> tuple[tuple[str, ReadinessCheck], ...]:
        return (("database", unavailable),)

    app.dependency_overrides[get_readiness_checks] = failing_checks
    response = await client.get("/health/ready")
    metrics = await client.get("/metrics")

    assert response.status_code == 503
    assert 'nexus_dependency_ready{dependency="database"} 0.0' in metrics.text


async def test_http_trace_correlates_request_id_without_headers_or_body(
    app: FastAPI, client: AsyncClient
) -> None:
    exporter = InMemorySpanExporter()
    app.state.telemetry.tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    response = await client.get(
        "/api/v1", headers={"X-Request-ID": "controlled-trace-request"}
    )
    spans = exporter.get_finished_spans()
    server_span = next(span for span in spans if span.kind.name == "SERVER")
    attributes = server_span.attributes

    assert response.status_code == 200
    assert attributes is not None
    assert attributes["request.id"] == "controlled-trace-request"
    serialized_attributes = json.dumps(dict(attributes))
    assert "authorization" not in serialized_attributes.lower()
    assert "controlled-trace-request" in serialized_attributes


def test_json_logging_drops_customer_and_secret_fields_and_adds_trace_ids() -> None:
    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="nexus.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="safe message",
        args=(),
        exc_info=None,
    )
    record.event = "controlled_test"
    record.authorization = "Bearer private-token"
    record.organization_id = "private-tenant"
    record.user_id = "private-user"

    with tracer.start_as_current_span("safe-test-span"):
        payload = json.loads(formatter.format(record))

    assert payload["event"] == "controlled_test"
    assert len(payload["trace_id"]) == 32
    assert len(payload["span_id"]) == 16
    assert "authorization" not in payload
    assert "organization_id" not in payload
    assert "user_id" not in payload
    assert "private-token" not in json.dumps(payload)


def test_database_operation_labels_are_bounded() -> None:
    assert _bounded_operation(" SELECT * FROM private_table") == "select"
    assert _bounded_operation("INSERT INTO private_table VALUES (1)") == "insert"
    assert _bounded_operation("CREATE EXTENSION vector") == "other"
    assert _bounded_operation("") == "other"


def test_worker_success_and_failure_metrics_do_not_label_job_ids() -> None:
    class Task:
        name = "nexus.background.execute_job"

    task_started(task_id="private-job-1", task=Task())
    task_finished(task_id="private-job-1", task=Task(), state="SUCCESS")
    task_started(task_id="private-job-2", task=Task())
    task_finished(task_id="private-job-2", task=Task(), state="FAILURE")
    payload = generate_latest(registry).decode()

    assert 'status="success",task="nexus.background.execute_job"' in payload
    assert 'status="failure",task="nexus.background.execute_job"' in payload
    assert "private-job" not in payload
