"""SQLAlchemy persistence adapter for authentication."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.models import PasswordResetToken, RefreshSession, User


class AuthRepository:
    """Persist authentication state inside a caller-owned transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def user_by_email(self, email: str) -> User | None:
        return await self._session.scalar(select(User).where(User.email == email))

    async def user_by_id(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)

    def add_user(self, user: User) -> None:
        self._session.add(user)

    def add_refresh_session(self, refresh_session: RefreshSession) -> None:
        self._session.add(refresh_session)

    async def locked_refresh_session(self, session_id: UUID) -> RefreshSession | None:
        statement = select(RefreshSession).where(RefreshSession.id == session_id).with_for_update()
        return await self._session.scalar(statement)

    async def revoke_user_sessions(self, user_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )

    def add_password_reset(self, reset: PasswordResetToken) -> None:
        self._session.add(reset)

    async def locked_password_reset(self, digest: str) -> PasswordResetToken | None:
        return await self._session.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_digest == digest)
            .with_for_update()
        )

    async def consume_password_resets(self, user_id: UUID, used_at: datetime) -> None:
        """Invalidate every outstanding reset grant after one succeeds."""
        await self._session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
            .values(used_at=used_at)
        )
