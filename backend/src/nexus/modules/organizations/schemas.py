"""Organization HTTP transport schemas."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
Slug = Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]


class OrganizationCreateRequest(BaseModel):
    name: Name
    slug: Slug


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    role: Literal["owner", "admin", "member"]
    created_at: datetime


class OrganizationPageResponse(BaseModel):
    items: list[OrganizationResponse]
    page: int
    page_size: int
    total: int


class InvitationCreateRequest(BaseModel):
    email: Annotated[
        str, Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    ]
    role: Literal["admin", "member"] = "member"


class MembershipResponse(BaseModel):
    organization_id: UUID
    user_id: UUID
    role: Literal["owner", "admin", "member"]
    status: Literal["pending", "active"]
    created_at: datetime


class BranchCreateRequest(BaseModel):
    name: Name
    slug: Slug


class BranchUpdateRequest(BaseModel):
    name: Name | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "BranchUpdateRequest":
        if self.name is None and self.is_active is None:
            raise ValueError("At least one branch field must be provided")
        return self


class BranchResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class BranchPageResponse(BaseModel):
    items: list[BranchResponse]
    page: int
    page_size: int
    total: int
