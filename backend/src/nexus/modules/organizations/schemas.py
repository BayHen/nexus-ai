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
    role: Literal["owner", "admin", "manager", "staff", "viewer"]
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
    role: Literal["admin", "manager", "staff", "viewer"] = "viewer"


class MembershipResponse(BaseModel):
    organization_id: UUID
    user_id: UUID
    role: Literal["owner", "admin", "manager", "staff", "viewer"]
    status: Literal["pending", "active"]
    created_at: datetime


class MemberResponse(MembershipResponse):
    email: str


class MemberPageResponse(BaseModel):
    items: list[MemberResponse]
    page: int
    page_size: int
    total: int


class MemberRoleUpdateRequest(BaseModel):
    role: Literal["owner", "admin", "manager", "staff", "viewer"]


class AuditEventResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    event_type: str
    target_type: str
    target_id: UUID | None
    details: dict[str, object]
    created_at: datetime


class AuditEventPageResponse(BaseModel):
    items: list[AuditEventResponse]
    page: int
    page_size: int
    total: int


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
