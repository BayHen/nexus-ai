"""Authentication domain values and errors."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class AuthenticationFailedError(Exception):
    """Raised for any credential failure without revealing which input failed."""


class TokenInvalidError(Exception):
    """Raised when a token is invalid, expired, revoked, or replayed."""


class RefreshTokenReplayError(TokenInvalidError):
    """Raised after revoking a refresh-token family due to replay."""


class EmailAlreadyRegisteredError(Exception):
    """Raised when registration conflicts with an existing normalized email."""


@dataclass(frozen=True)
class AuthenticatedUser:
    """Identity extracted from a valid access token."""

    user_id: UUID
    email: str


@dataclass(frozen=True)
class TokenPair:
    """Access and rotating refresh credentials returned once to the caller."""

    access_token: str
    refresh_token: str
    access_expires_at: datetime
