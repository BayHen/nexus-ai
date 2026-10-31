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
    CATALOG_READ = "catalog:read"
    CATALOG_WRITE = "catalog:write"
    CATALOG_DELETE = "catalog:delete"
    INVENTORY_READ = "inventory:read"
    INVENTORY_MANAGE = "inventory:manage"
    INVENTORY_ADJUST = "inventory:adjust"
    INVENTORY_POLICY = "inventory:policy"
    ORDER_READ = "order:read"
    ORDER_WRITE = "order:write"
    ORDER_CONFIRM = "order:confirm"
    ORDER_CANCEL = "order:cancel"
    PAYMENT_READ = "payment:read"
    PAYMENT_WRITE = "payment:write"
    PAYMENT_REFUND = "payment:refund"


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
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.CATALOG_DELETE,
            Permission.INVENTORY_READ,
            Permission.INVENTORY_MANAGE,
            Permission.INVENTORY_ADJUST,
            Permission.INVENTORY_POLICY,
            Permission.ORDER_READ,
            Permission.ORDER_WRITE,
            Permission.ORDER_CONFIRM,
            Permission.ORDER_CANCEL,
            Permission.PAYMENT_READ,
            Permission.PAYMENT_WRITE,
            Permission.PAYMENT_REFUND,
        }
    ),
    "manager": frozenset(
        {
            Permission.BRANCH_READ,
            Permission.BRANCH_CREATE,
            Permission.BRANCH_UPDATE,
            Permission.MEMBER_READ,
            Permission.AUDIT_READ,
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.INVENTORY_READ,
            Permission.INVENTORY_MANAGE,
            Permission.INVENTORY_ADJUST,
            Permission.ORDER_READ,
            Permission.ORDER_WRITE,
            Permission.ORDER_CONFIRM,
            Permission.ORDER_CANCEL,
            Permission.PAYMENT_READ,
            Permission.PAYMENT_WRITE,
        }
    ),
    "staff": frozenset(
        {
            Permission.BRANCH_READ,
            Permission.BRANCH_UPDATE,
            Permission.CATALOG_READ,
            Permission.INVENTORY_READ,
            Permission.INVENTORY_ADJUST,
            Permission.ORDER_READ,
            Permission.ORDER_WRITE,
            Permission.ORDER_CONFIRM,
            Permission.PAYMENT_READ,
        }
    ),
    "viewer": frozenset(
        {
            Permission.BRANCH_READ,
            Permission.CATALOG_READ,
            Permission.INVENTORY_READ,
            Permission.ORDER_READ,
        }
    ),
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
