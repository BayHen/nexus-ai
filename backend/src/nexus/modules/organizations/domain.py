"""Organization domain values and errors."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

MembershipRole = Literal["owner", "admin", "member"]


class OrganizationNotFoundError(Exception):
    """Raised when an organization is not visible to the actor."""


class TenantContextRequiredError(Exception):
    """Raised when a business operation has no active tenant."""


class TenantAccessDeniedError(Exception):
    """Raised when an authenticated actor lacks a tenant permission."""


class OrganizationConflictError(Exception):
    """Raised when an organization invariant conflicts with stored state."""


class InvitationConflictError(Exception):
    """Raised when a membership invitation cannot be created or accepted."""


@dataclass(frozen=True)
class TenantContext:
    """Server-resolved tenant identity used by business operations."""

    organization_id: UUID
    user_id: UUID
    role: MembershipRole
