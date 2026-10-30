"""Security-focused tests for authentication primitives."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from nexus.bootstrap.config import Settings
from nexus.modules.auth.domain import TokenInvalidError
from nexus.modules.auth.rate_limit import AuthenticationRateLimiter
from nexus.modules.auth.security import (
    create_access_token,
    decode_access_token,
    digest_opaque_token,
    hash_password,
    verify_password,
)


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+asyncpg://unused:unused@localhost/unused",
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        _env_file=None,
    )


def test_password_uses_argon2id_and_verifies_without_plaintext() -> None:
    password_hash = hash_password("correct horse battery staple")
    assert password_hash.startswith("$argon2id$")
    assert "correct horse" not in password_hash
    assert verify_password(password_hash, "correct horse battery staple") is True
    assert verify_password(password_hash, "incorrect password") is False


def test_access_token_accepts_valid_and_rejects_tampered_token(auth_settings: Settings) -> None:
    user_id = uuid4()
    token, _ = create_access_token(user_id, "user@example.com", auth_settings)
    assert decode_access_token(token, auth_settings)["sub"] == str(user_id)

    with pytest.raises(TokenInvalidError):
        decode_access_token(f"{token}tampered", auth_settings)


def test_access_token_rejects_expired_token(auth_settings: Settings) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "email": "user@example.com",
            "type": "access",
            "jti": str(uuid4()),
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "iss": auth_settings.jwt_issuer,
            "aud": auth_settings.jwt_audience,
        },
        auth_settings.jwt_secret_key.get_secret_value(),
        algorithm=auth_settings.jwt_algorithm,
    )
    with pytest.raises(TokenInvalidError):
        decode_access_token(token, auth_settings)


def test_refresh_digest_does_not_contain_token() -> None:
    token = "opaque-refresh-secret"
    digest = digest_opaque_token(token)
    assert token not in digest
    assert len(digest) == 64


@pytest.mark.anyio
async def test_authentication_rate_limiter_blocks_and_resets() -> None:
    limiter = AuthenticationRateLimiter(attempts=2, window_seconds=60)
    assert await limiter.allow("client:user") is True
    assert await limiter.allow("client:user") is True
    assert await limiter.allow("client:user") is False
    await limiter.reset("client:user")
    assert await limiter.allow("client:user") is True
