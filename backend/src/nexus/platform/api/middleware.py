"""HTTP middleware for correlation and access logging."""

import logging
import re
from collections.abc import Sequence
from time import perf_counter
from typing import Any
from uuid import uuid4

from opentelemetry import trace
from starlette.datastructures import Headers, MutableHeaders
from starlette.routing import compile_path
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nexus.platform.api.request_context import (
    REQUEST_ID_HEADER,
    reset_request_id,
    set_request_id,
)
from nexus.platform.observability.metrics import ApplicationMetrics

logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def resolve_request_id(candidate: str | None) -> str:
    """Use a safe caller-provided ID or generate a new correlation ID."""
    if candidate and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid4())


class RequestContextMiddleware:
    """Attach a request ID and emit one structured completion log per request."""

    def __init__(
        self,
        app: ASGIApp,
        metrics: ApplicationMetrics,
        routes: Sequence[str],
    ) -> None:
        self.app = app
        self.metrics = metrics
        self.routes = tuple((template, compile_path(template)[0]) for template in routes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        state: dict[str, Any] = scope.setdefault("state", {})
        traced_request_id = state.get("request_id")
        request_id = (
            traced_request_id
            if isinstance(traced_request_id, str)
            else resolve_request_id(headers.get(REQUEST_ID_HEADER))
        )
        state["request_id"] = request_id
        token = set_request_id(request_id)
        started_at = perf_counter()
        status_code = 500
        self.metrics.http_in_progress.inc()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_seconds = perf_counter() - started_at
            duration_ms = round(duration_seconds * 1000, 3)
            route = self._resolve_route(scope)
            if route != "/metrics":
                self.metrics.observe_http(
                    scope["method"], route, status_code, duration_seconds
                )
            self.metrics.http_in_progress.dec()
            span = trace.get_current_span()
            if span.is_recording():
                span.set_attribute("request.id", request_id)
                span.set_attribute("http.route", route)
            logger.info(
                "Request completed",
                extra={
                    "event": "request_completed",
                    "request_id": request_id,
                    "http_method": scope["method"],
                    "http_route": route,
                    "http_status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            reset_request_id(token)

    def _resolve_route(self, scope: Scope) -> str:
        path = scope["path"]
        for template, pattern in self.routes:
            if pattern.match(path):
                return template
        return "unmatched"
