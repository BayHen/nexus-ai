"""Shared transport models."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Stable machine-readable API error body."""

    code: str
    message: str
    request_id: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    """Top-level API error envelope."""

    error: ErrorBody


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: Literal["alive", "ready", "not_ready"]
    checks: dict[str, Literal["up", "down"]] | None = None


class ApiInfoResponse(BaseModel):
    """Versioned API metadata."""

    name: str = Field(examples=["NEXUS AI API"])
    version: str = Field(examples=["v1"])
