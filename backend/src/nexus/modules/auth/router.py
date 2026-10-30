"""Versioned authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.bootstrap.config import Settings
from nexus.modules.auth.dependencies import (
    get_auth_rate_limiter,
    get_auth_settings,
    get_current_user,
    get_transaction,
)
from nexus.modules.auth.domain import (
    AuthenticatedUser,
    AuthenticationFailedError,
    EmailAlreadyRegisteredError,
    RefreshTokenReplayError,
    TokenInvalidError,
    TokenPair,
)
from nexus.modules.auth.rate_limit import AuthenticationRateLimiter
from nexus.modules.auth.schemas import (
    AuthenticationResponse,
    CredentialsRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from nexus.modules.auth.service import AuthService, normalize_email
from nexus.platform.api.errors import ApplicationError

router = APIRouter(prefix="/auth", tags=["authentication"])
GENERIC_AUTH_ERROR = "Authentication failed."
INVALID_TOKEN_ERROR = "The authentication token is invalid or expired."
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]
SettingsDependency = Annotated[Settings, Depends(get_auth_settings)]
LimiterDependency = Annotated[AuthenticationRateLimiter, Depends(get_auth_rate_limiter)]
CurrentUserDependency = Annotated[AuthenticatedUser, Depends(get_current_user)]


def token_response(pair: TokenPair) -> TokenResponse:
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_at=pair.access_expires_at,
    )


@router.post(
    "/register", response_model=AuthenticationResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    body: CredentialsRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> AuthenticationResponse:
    try:
        user, pair = await AuthService(session, settings).register(body.email, body.password)
    except (EmailAlreadyRegisteredError, IntegrityError) as exc:
        raise ApplicationError(
            code="registration_unavailable",
            message="Unable to complete registration.",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc
    return AuthenticationResponse(
        user=UserResponse(id=user.id, email=user.email), tokens=token_response(pair)
    )


@router.post("/login", response_model=AuthenticationResponse)
async def login(
    request: Request,
    body: CredentialsRequest,
    session: SessionDependency,
    settings: SettingsDependency,
    limiter: LimiterDependency,
) -> AuthenticationResponse:
    key = (
        f"login:{request.client.host if request.client else 'unknown'}:"
        f"{normalize_email(body.email)}"
    )
    if not await limiter.allow(key):
        raise ApplicationError(
            code="authentication_rate_limited",
            message=GENERIC_AUTH_ERROR,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    try:
        user, pair = await AuthService(session, settings).login(body.email, body.password)
    except AuthenticationFailedError as exc:
        raise ApplicationError(
            code="authentication_failed",
            message=GENERIC_AUTH_ERROR,
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    await limiter.reset(key)
    return AuthenticationResponse(
        user=UserResponse(id=user.id, email=user.email), tokens=token_response(pair)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> TokenResponse:
    try:
        return token_response(await AuthService(session, settings).rotate(body.refresh_token))
    except RefreshTokenReplayError as exc:
        # Persist family revocation before returning the generic replay error.
        await session.commit()
        raise ApplicationError(
            code="invalid_authentication_token",
            message=INVALID_TOKEN_ERROR,
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    except TokenInvalidError as exc:
        raise ApplicationError(
            code="invalid_authentication_token",
            message=INVALID_TOKEN_ERROR,
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: RefreshRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> MessageResponse:
    try:
        await AuthService(session, settings).logout(body.refresh_token)
    except TokenInvalidError as exc:
        raise ApplicationError(
            code="invalid_authentication_token",
            message=INVALID_TOKEN_ERROR,
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    return MessageResponse(message="The session has been invalidated.")


@router.get("/me", response_model=UserResponse)
async def me(current: CurrentUserDependency) -> UserResponse:
    return UserResponse(id=current.user_id, email=current.email)


@router.post("/password-reset/request", response_model=MessageResponse, status_code=202)
async def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    session: SessionDependency,
    settings: SettingsDependency,
    limiter: LimiterDependency,
) -> MessageResponse:
    key = (
        f"password-reset:{request.client.host if request.client else 'unknown'}:"
        f"{normalize_email(body.email)}"
    )
    if await limiter.allow(key):
        await AuthService(session, settings).request_password_reset(body.email)
    return MessageResponse(
        message="If the account exists, password reset instructions will be sent."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    body: PasswordResetConfirmRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> MessageResponse:
    try:
        await AuthService(session, settings).reset_password(body.token, body.new_password)
    except TokenInvalidError as exc:
        raise ApplicationError(
            code="invalid_password_reset_token",
            message="The password reset token is invalid or expired.",
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc
    return MessageResponse(message="The password has been reset.")
