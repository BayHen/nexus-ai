"""Cryptographic primitives for authentication."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from nexus.bootstrap.config import Settings
from nexus.modules.auth.domain import TokenInvalidError

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
DUMMY_PASSWORD_HASH = password_hasher.hash("nexus-ai-dummy-password-for-timing-equalization")


def hash_password(password: str) -> str:
    """Hash a password using Argon2id with an automatically generated salt."""
    return password_hasher.hash(password)


def verify_password(password_hash: str, candidate: str) -> bool:
    """Verify without propagating parser or mismatch details."""
    try:
        return password_hasher.verify(password_hash, candidate)
    except (VerificationError, InvalidHashError):
        return False


def digest_opaque_token(token: str) -> str:
    """Create a fixed-length digest suitable for server-side token lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_opaque_token() -> str:
    """Return a URL-safe token with 256 bits of entropy."""
    return secrets.token_urlsafe(32)


def create_access_token(user_id: UUID, email: str, settings: Settings) -> tuple[str, datetime]:
    """Create a signed, audience-bound short-lived access token."""
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "jti": str(uuid4()),
        "iat": issued_at,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    encoded = jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return encoded, expires_at


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Validate signature, lifetime, issuer, audience, and token type."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "email", "type", "jti", "iat", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalidError from exc
    if payload.get("type") != "access":
        raise TokenInvalidError
    return payload
