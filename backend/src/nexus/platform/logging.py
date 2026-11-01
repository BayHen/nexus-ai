"""Structured JSON logging configuration."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace

from nexus.platform.api.request_context import get_request_id

RESERVED_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)
SAFE_EXTRA_FIELDS = frozenset(
    {
        "event",
        "request_id",
        "correlation_id",
        "http_method",
        "http_route",
        "http_status_code",
        "duration_ms",
        "error_type",
        "task_name",
        "attempt_count",
        "max_attempts",
        "countdown_seconds",
        "event_type",
        "event_count",
        "finding_count",
    }
)


class JsonFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", get_request_id()),
        }
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = format(span_context.trace_id, "032x")
            payload["span_id"] = format(span_context.span_id, "016x")
        for key, value in record.__dict__.items():
            if (
                key not in RESERVED_LOG_RECORD_FIELDS
                and key in SAFE_EXTRA_FIELDS
                and key not in payload
            ):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(log_level: str) -> None:
    """Configure the root logger for structured application output."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
