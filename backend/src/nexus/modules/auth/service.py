"""Transaction-aware authentication use cases."""

import asyncio
import hmac
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from nexus.bootstrap.config import Settings
from nexus.modules.auth.domain import (
    AuthenticationFailedError,
    EmailAlreadyRegisteredError,
    RefreshTokenReplayError,
    TokenInvalidError,
    TokenPair,
)
from nexus.modules.auth.models import PasswordResetToken, RefreshSession, User
from nexus.modules.auth.repository import AuthRepository
from nexus.modules.auth.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    digest_opaque_token,
    hash_password,
    new_opaque_token,
    verify_password,
)

logger = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    """Normalize the case-insensitive login identifier."""
    return email.strip().casefold()


class AuthService:
    """Execute authentication operations inside one database transaction."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repository = AuthRepository(session)

    async def register(self, email: str, password: str) -> tuple[User, TokenPair]:
        normalized = normalize_email(email)
        if await self._repository.user_by_email(normalized) is not None:
            raise EmailAlreadyRegisteredError
        user = User(
            email=normalized, password_hash=await asyncio.to_thread(hash_password, password)
        )
        self._repository.add_user(user)
        await self._session.flush()
        pair = await self._new_token_pair(user)
        self._audit("auth.registration_succeeded", user_id=user.id)
        return user, pair

    async def login(self, email: str, password: str) -> tuple[User, TokenPair]:
        user = await self._repository.user_by_email(normalize_email(email))
        hash_to_verify = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
        password_valid = await asyncio.to_thread(verify_password, hash_to_verify, password)
        if user is None or not user.is_active or not password_valid:
            self._audit("auth.login_failed")
            raise AuthenticationFailedError
        pair = await self._new_token_pair(user)
        self._audit("auth.login_succeeded", user_id=user.id)
        return user, pair

    async def rotate(self, refresh_token: str) -> TokenPair:
        session_id, secret = self._parse_refresh_token(refresh_token)
        current = await self._repository.locked_refresh_session(session_id)
        now = datetime.now(UTC)
        if current is None:
            raise TokenInvalidError
        invalid = (
            current.revoked_at is not None
            or current.expires_at <= now
            or not hmac.compare_digest(current.token_digest, digest_opaque_token(secret))
        )
        if invalid:
            if current.revoked_at is not None:
                await self._repository.revoke_user_sessions(current.user_id, now)
                self._audit("auth.refresh_replay_detected", user_id=current.user_id)
                raise RefreshTokenReplayError
            raise TokenInvalidError
        user = await self._repository.user_by_id(current.user_id)
        if user is None or not user.is_active:
            raise TokenInvalidError
        replacement = await self._new_token_pair(user)
        current.revoked_at = now
        current.replaced_by_id = UUID(replacement.refresh_token.split(".", 1)[0])
        self._audit("auth.refresh_rotated", user_id=user.id, session_id=current.id)
        return replacement

    async def logout(self, refresh_token: str) -> None:
        session_id, secret = self._parse_refresh_token(refresh_token)
        current = await self._repository.locked_refresh_session(session_id)
        if current is None or not hmac.compare_digest(
            current.token_digest, digest_opaque_token(secret)
        ):
            raise TokenInvalidError
        if current.revoked_at is None:
            current.revoked_at = datetime.now(UTC)
        self._audit("auth.logout_succeeded", user_id=current.user_id, session_id=current.id)

    async def request_password_reset(self, email: str) -> str | None:
        user = await self._repository.user_by_email(normalize_email(email))
        if user is None or not user.is_active:
            self._audit("auth.password_reset_requested_unknown")
            return None
        token = new_opaque_token()
        self._repository.add_password_reset(
            PasswordResetToken(
                user_id=user.id,
                token_digest=digest_opaque_token(token),
                expires_at=datetime.now(UTC)
                + timedelta(minutes=self._settings.password_reset_expire_minutes),
            )
        )
        self._audit("auth.password_reset_requested", user_id=user.id)
        return token

    async def reset_password(self, token: str, new_password: str) -> None:
        reset = await self._repository.locked_password_reset(digest_opaque_token(token))
        now = datetime.now(UTC)
        if reset is None or reset.used_at is not None or reset.expires_at <= now:
            raise TokenInvalidError
        user = await self._repository.user_by_id(reset.user_id)
        if user is None or not user.is_active:
            raise TokenInvalidError
        user.password_hash = await asyncio.to_thread(hash_password, new_password)
        await self._repository.consume_password_resets(user.id, now)
        await self._repository.revoke_user_sessions(user.id, now)
        self._audit("auth.password_reset_succeeded", user_id=user.id)

    async def _new_token_pair(self, user: User) -> TokenPair:
        access_token, expires_at = create_access_token(user.id, user.email, self._settings)
        secret = new_opaque_token()
        refresh = RefreshSession(
            user_id=user.id,
            token_digest=digest_opaque_token(secret),
            expires_at=datetime.now(UTC) + timedelta(days=self._settings.refresh_token_expire_days),
        )
        self._repository.add_refresh_session(refresh)
        await self._session.flush()
        return TokenPair(access_token, f"{refresh.id}.{secret}", expires_at)

    @staticmethod
    def _parse_refresh_token(token: str) -> tuple[UUID, str]:
        try:
            raw_id, secret = token.split(".", 1)
            if not secret:
                raise ValueError
            return UUID(raw_id), secret
        except (ValueError, AttributeError) as exc:
            raise TokenInvalidError from exc

    @staticmethod
    def _audit(event: str, **metadata: object) -> None:
        logger.info("Authentication audit event", extra={"event": event, **metadata})
