"""Unit tests for the explicit tenant permission matrix."""

import pytest

from nexus.modules.organizations.domain import MembershipRole, Permission, has_permission


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        ("owner", Permission.MEMBER_ROLE_MANAGE, True),
        ("admin", Permission.MEMBER_ROLE_MANAGE, True),
        ("manager", Permission.MEMBER_ROLE_MANAGE, False),
        ("manager", Permission.BRANCH_CREATE, True),
        ("staff", Permission.BRANCH_CREATE, False),
        ("staff", Permission.BRANCH_UPDATE, True),
        ("viewer", Permission.BRANCH_READ, True),
        ("viewer", Permission.BRANCH_UPDATE, False),
        ("viewer", Permission.AUDIT_READ, False),
    ],
)
def test_permission_matrix(role: MembershipRole, permission: Permission, *, allowed: bool) -> None:
    assert has_permission(role, permission) is allowed
