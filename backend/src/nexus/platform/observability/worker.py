"""Celery worker metrics and tracing hooks."""

from __future__ import annotations

from threading import Lock
from time import perf_counter
from typing import Any

from celery import signals  # type: ignore[import-untyped]
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server

from nexus.bootstrap.config import Settings
from nexus.platform.observability.telemetry import Telemetry, configure_telemetry

registry = CollectorRegistry(auto_describe=True)
tasks = Counter(
    "nexus_worker_tasks_total",
    "Celery tasks by bounded task name and outcome.",
    ("task", "status"),
    registry=registry,
)
duration = Histogram(
    "nexus_worker_task_duration_seconds",
    "Celery task execution latency.",
    ("task",),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
    registry=registry,
)
active = Gauge(
    "nexus_worker_tasks_active",
    "Celery tasks currently executing.",
    registry=registry,
)
_started: dict[str, tuple[float, str]] = {}
_lock = Lock()
_telemetry: Telemetry | None = None


def _task_name(task: Any) -> str:
    name = getattr(task, "name", "unknown")
    return name if name == "nexus.background.execute_job" else "other"


@signals.worker_process_init.connect(weak=False)  # type: ignore[untyped-decorator]
def initialize_worker_tracing(**_: Any) -> None:
    global _telemetry
    settings = Settings()
    _telemetry = configure_telemetry(settings)
    CeleryInstrumentor().instrument(  # type: ignore[no-untyped-call]
        tracer_provider=_telemetry.tracer_provider
    )


@signals.worker_process_shutdown.connect(weak=False)  # type: ignore[untyped-decorator]
def shutdown_worker_tracing(**_: Any) -> None:
    if _telemetry is not None:
        _telemetry.shutdown()


@signals.worker_ready.connect(weak=False)  # type: ignore[untyped-decorator]
def start_worker_metrics(**_: Any) -> None:
    settings = Settings()
    start_http_server(settings.worker_metrics_port, registry=registry)


@signals.task_prerun.connect(weak=False)  # type: ignore[untyped-decorator]
def task_started(task_id: str | None = None, task: Any = None, **_: Any) -> None:
    if task_id is None:
        return
    with _lock:
        _started[task_id] = (perf_counter(), _task_name(task))
    active.inc()


@signals.task_postrun.connect(weak=False)  # type: ignore[untyped-decorator]
def task_finished(
    task_id: str | None = None,
    task: Any = None,
    state: str | None = None,
    **_: Any,
) -> None:
    if task_id is None:
        return
    with _lock:
        started = _started.pop(task_id, None)
    if started is None:
        return
    started_at, task_name = started
    status = "success" if state == "SUCCESS" else "retry" if state == "RETRY" else "failure"
    tasks.labels(task_name, status).inc()
    duration.labels(task_name).observe(perf_counter() - started_at)
    active.dec()
