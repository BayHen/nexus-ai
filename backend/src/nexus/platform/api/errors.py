"""Centralized API exception mapping."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from nexus.platform.api.models import ErrorBody, ErrorResponse
from nexus.platform.api.request_context import get_request_id

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    """Base exception for errors safe to expose through the API."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            request_id=get_request_id(request),
            details=details,
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


async def handle_application_error(request: Request, exc: ApplicationError) -> JSONResponse:
    """Map a known application error to its public representation."""
    return _error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map request validation failures without leaking internal exception data."""
    details = [
        {
            "location": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return _error_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="request_validation_failed",
        message="The request is invalid.",
        details=details,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures and return a non-sensitive error response."""
    logger.exception(
        "Unhandled request error",
        extra={"event": "unhandled_request_error", "request_id": get_request_id(request)},
    )
    return _error_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_server_error",
        message="An unexpected error occurred.",
    )


ExceptionHandler = Callable[[Request, Any], Awaitable[JSONResponse]]


def register_exception_handlers(application: FastAPI) -> None:
    """Register the application's centralized exception handlers."""
    application.add_exception_handler(ApplicationError, handle_application_error)  # type: ignore[arg-type]
    application.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, handle_unexpected_error)
