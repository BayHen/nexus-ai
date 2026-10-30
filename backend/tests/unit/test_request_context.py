"""Tests for request correlation helpers."""

from uuid import UUID

from nexus.platform.api.middleware import resolve_request_id


def test_safe_request_id_is_preserved() -> None:
    assert resolve_request_id("client-request_123") == "client-request_123"


def test_unsafe_request_id_is_replaced() -> None:
    generated = resolve_request_id("contains spaces")

    assert str(UUID(generated)) == generated
