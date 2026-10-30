"""HTTP middleware for correlation and access logging."""

import logging
import re
from time import perf_counter
from typing import Any
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nexus.platform.api.request_context import (
    REQUEST_ID_HEADER,
    reset_request_id,
    set_request_id,
)

logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def resolve_request_id(candidate: str | None) -> str:
    """Use a safe caller-provided ID or generate a new correlation ID."""
    if candidate and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid4())


class RequestContextMiddleware:
    """Attach a request ID and emit one structured completion log per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = resolve_request_id(headers.get(REQUEST_ID_HEADER))
        state: dict[str, Any] = scope.setdefault("state", {})
        state["request_id"] = request_id
        token = set_request_id(request_id)
        started_at = perf_counter()
        status_code = 500

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
            duration_ms = round((perf_counter() - started_at) * 1000, 3)
            logger.info(
                "Request completed",
                extra={
                    "event": "request_completed",
                    "request_id": request_id,
                    "http_method": scope["method"],
                    "http_path": scope["path"],
                    "http_status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            reset_request_id(token)
