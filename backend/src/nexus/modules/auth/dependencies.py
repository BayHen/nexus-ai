"""FastAPI dependencies for authentication."""

from collections.abc import AsyncIterator
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.bootstrap.config import Settings
from nexus.modules.auth.domain import AuthenticatedUser, TokenInvalidError
from nexus.modules.auth.rate_limit import AuthenticationRateLimiter
from nexus.modules.auth.security import decode_access_token
from nexus.platform.api.errors import ApplicationError
from nexus.platform.cache.service import CacheService
from nexus.platform.database.protocols import TransactionManagerProtocol

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_auth_rate_limiter(request: Request) -> AuthenticationRateLimiter:
    return cast(AuthenticationRateLimiter, request.app.state.auth_rate_limiter)


async def get_transaction(request: Request) -> AsyncIterator[AsyncSession]:
    manager = cast(TransactionManagerProtocol, request.app.state.database_manager)
    async with manager.transaction() as session:
        yield session
        keys = set(session.info.get("cache_invalidation_keys", set()))
    cache = cast(CacheService, request.app.state.cache_service)
    for key in keys:
        await cache.delete(key)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_auth_settings)],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApplicationError(
            code="invalid_authentication_token",
            message="The authentication token is invalid or expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        payload = decode_access_token(credentials.credentials, settings)
        return AuthenticatedUser(user_id=UUID(payload["sub"]), email=str(payload["email"]))
    except (TokenInvalidError, ValueError, KeyError, TypeError) as exc:
        raise ApplicationError(
            code="invalid_authentication_token",
            message="The authentication token is invalid or expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
