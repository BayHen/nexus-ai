"""End-to-end authentication API tests against PostgreSQL."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings
from nexus.modules.auth.models import PasswordResetToken, RefreshSession, User
from nexus.modules.auth.security import digest_opaque_token
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_migrations import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PASSWORD = "correct horse battery staple"


@pytest.fixture
def migrated_auth_database_url(temporary_database_url: str) -> str:
    command.upgrade(alembic_config(temporary_database_url), "head")
    return temporary_database_url


@pytest.fixture
async def auth_client(migrated_auth_database_url: str) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment="test",
        database_url=migrated_auth_database_url,
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        auth_rate_limit_attempts=2,
        _env_file=None,
    )
    manager = DatabaseManager(migrated_auth_database_url, 3)
    app = create_app(settings, manager)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await manager.dispose()


async def register(auth_client: AsyncClient, email: str = "user@example.com") -> dict[str, Any]:
    response = await auth_client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


async def test_register_login_me_refresh_rotation_logout(auth_client: AsyncClient) -> None:
    registered = await register(auth_client)
    access_token = registered["tokens"]["access_token"]
    first_refresh = registered["tokens"]["refresh_token"]

    me = await auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"

    rotated = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert rotated.status_code == 200
    second_refresh = rotated.json()["refresh_token"]
    assert second_refresh != first_refresh

    replay = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert replay.status_code == 401

    replay_revoked_family = await auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second_refresh}
    )
    assert replay_revoked_family.status_code == 401

    logged_in = await auth_client.post(
        "/api/v1/auth/login", json={"email": "USER@example.com", "password": PASSWORD}
    )
    assert logged_in.status_code == 200
    login_refresh = logged_in.json()["tokens"]["refresh_token"]
    logout = await auth_client.post("/api/v1/auth/logout", json={"refresh_token": login_refresh})
    assert logout.status_code == 200
    revoked = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": login_refresh})
    assert revoked.status_code == 401


async def test_generic_login_errors_and_rate_limit(auth_client: AsyncClient) -> None:
    await register(auth_client)
    payloads = [
        {"email": "missing@example.com", "password": PASSWORD},
        {"email": "user@example.com", "password": "wrong-password-value"},
    ]
    responses = [await auth_client.post("/api/v1/auth/login", json=item) for item in payloads]
    assert [response.status_code for response in responses] == [401, 401]
    assert responses[0].json()["error"]["message"] == responses[1].json()["error"]["message"]

    await auth_client.post("/api/v1/auth/login", json=payloads[1])
    limited = await auth_client.post("/api/v1/auth/login", json=payloads[1])
    assert limited.status_code == 429


async def test_invalid_access_and_refresh_tokens_are_rejected(auth_client: AsyncClient) -> None:
    invalid_access = await auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"}
    )
    invalid_refresh = await auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": f"{'0' * 36}.{'x' * 32}"}
    )
    assert invalid_access.status_code == 401
    assert invalid_refresh.status_code == 401


async def test_password_reset_request_is_generic(auth_client: AsyncClient) -> None:
    await register(auth_client)
    known = await auth_client.post(
        "/api/v1/auth/password-reset/request", json={"email": "user@example.com"}
    )
    unknown = await auth_client.post(
        "/api/v1/auth/password-reset/request", json={"email": "missing@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


async def test_password_reset_is_single_use_and_revokes_sessions(
    auth_client: AsyncClient, migrated_auth_database_url: str
) -> None:
    registered = await register(auth_client)
    existing_refresh = registered["tokens"]["refresh_token"]
    reset_token = "known-test-reset-token-with-sufficient-entropy"
    manager = DatabaseManager(migrated_auth_database_url, 3)
    async with manager.transaction() as session:
        user = await session.scalar(select(User).where(User.email == "user@example.com"))
        assert user is not None
        refresh_session = await session.scalar(
            select(RefreshSession).where(RefreshSession.user_id == user.id)
        )
        assert refresh_session is not None
        assert PASSWORD not in user.password_hash
        assert existing_refresh.split(".", 1)[1] not in refresh_session.token_digest
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_digest=digest_opaque_token(reset_token),
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
    await manager.dispose()

    reset = await auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "a new secure password value"},
    )
    assert reset.status_code == 200
    reused = await auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "another secure password value"},
    )
    assert reused.status_code == 400
    revoked = await auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": existing_refresh}
    )
    assert revoked.status_code == 401
    old_login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": PASSWORD},
    )
    new_login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "a new secure password value"},
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200
