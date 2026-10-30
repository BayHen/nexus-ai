"""Authentication HTTP transport schemas."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

Email = Annotated[str, Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")]
Password = Annotated[str, Field(min_length=12, max_length=128)]


class CredentialsRequest(BaseModel):
    email: Email
    password: Password


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=40, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserResponse(BaseModel):
    id: UUID
    email: str


class AuthenticationResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class PasswordResetRequest(BaseModel):
    email: Email


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    new_password: Password


class MessageResponse(BaseModel):
    message: str
