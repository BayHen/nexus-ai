"""Organization domain values and errors."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal
from uuid import UUID

MembershipRole = Literal["owner", "admin", "manager", "staff", "viewer"]


class Permission(StrEnum):
    """Tenant-scoped capabilities enforced by application services."""

    BRANCH_READ = "branch:read"
    BRANCH_CREATE = "branch:create"
    BRANCH_UPDATE = "branch:update"
    MEMBER_READ = "member:read"
    MEMBER_INVITE = "member:invite"
    MEMBER_ROLE_MANAGE = "member:role:manage"
    MEMBER_REMOVE = "member:remove"
    AUDIT_READ = "audit:read"


ROLE_PERMISSIONS: dict[MembershipRole, frozenset[Permission]] = {
    "owner": frozenset(Permission),
    "admin": frozenset(
        {
            Permission.BRANCH_READ,
            Permission.BRANCH_CREATE,
            Permission.BRANCH_UPDATE,
            Permission.MEMBER_READ,
            Permission.MEMBER_INVITE,
            Permission.MEMBER_ROLE_MANAGE,
            Permission.MEMBER_REMOVE,
            Permission.AUDIT_READ,
        }
    ),
    "manager": frozenset(
        {
            Permission.BRANCH_READ,
            Permission.BRANCH_CREATE,
            Permission.BRANCH_UPDATE,
            Permission.MEMBER_READ,
            Permission.AUDIT_READ,
        }
    ),
    "staff": frozenset({Permission.BRANCH_READ, Permission.BRANCH_UPDATE}),
    "viewer": frozenset({Permission.BRANCH_READ}),
}


def has_permission(role: MembershipRole, permission: Permission) -> bool:
    """Return whether a role grants a capability."""
    return permission in ROLE_PERMISSIONS[role]


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


class LastOwnerProtectionError(Exception):
    """Raised when an operation would remove the final active owner."""


@dataclass(frozen=True)
class TenantContext:
    """Server-resolved tenant identity used by business operations."""

    organization_id: UUID
    user_id: UUID
    role: MembershipRole
