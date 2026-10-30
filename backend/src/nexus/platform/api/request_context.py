"""Request correlation helpers."""

from contextvars import ContextVar, Token

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str) -> Token[str | None]:
    """Set the request ID for the current execution context."""
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous request context."""
    request_id_context.reset(token)


def get_request_id(request: Request | None = None) -> str:
    """Resolve a request ID from request state or the current context."""
    if request is not None:
        request_id = getattr(request.state, "request_id", None)
        if isinstance(request_id, str):
            return request_id
    return request_id_context.get() or "unknown"
