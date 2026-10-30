"""Tenant-scoped RBAC and immutable audit integration tests."""

from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update
from sqlalchemy.exc import DBAPIError

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings
from nexus.modules.organizations.models import OrganizationAuditEvent
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_migrations import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PASSWORD = "correct horse battery staple"


@pytest.fixture
def rbac_database_url(temporary_database_url: str) -> str:
    command.upgrade(alembic_config(temporary_database_url), "head")
    return temporary_database_url


@pytest.fixture
async def rbac_client(rbac_database_url: str) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment="test",
        database_url=rbac_database_url,
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        _env_file=None,
    )
    manager = DatabaseManager(rbac_database_url, 3)
    app = create_app(settings, manager)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await manager.dispose()


async def register(client: AsyncClient, email: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    payload = cast(dict[str, Any], response.json())
    return str(payload["tokens"]["access_token"]), str(payload["user"]["id"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_organization(client: AsyncClient, token: str, slug: str) -> str:
    response = await client.post(
        "/api/v1/organizations",
        headers=auth(token),
        json={"name": f"Organization {slug}", "slug": slug},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def invite_and_accept(
    client: AsyncClient,
    owner_token: str,
    member_token: str,
    organization_id: str,
    email: str,
    role: str,
) -> None:
    invited = await client.post(
        "/api/v1/organizations/current/invitations",
        headers=auth(owner_token),
        json={"email": email, "role": role},
    )
    assert invited.status_code == 201, invited.text
    accepted = await client.post(
        f"/api/v1/organizations/{organization_id}/invitations/accept",
        headers=auth(member_token),
    )
    assert accepted.status_code == 200, accepted.text


async def test_permission_matrix_positive_and_negative_paths(rbac_client: AsyncClient) -> None:
    owner_token, _ = await register(rbac_client, "owner@example.com")
    admin_token, admin_id = await register(rbac_client, "admin@example.com")
    manager_token, manager_id = await register(rbac_client, "manager@example.com")
    staff_token, staff_id = await register(rbac_client, "staff@example.com")
    viewer_token, viewer_id = await register(rbac_client, "viewer@example.com")
    organization_id = await create_organization(rbac_client, owner_token, "permissions")

    for token, email, role in [
        (admin_token, "admin@example.com", "admin"),
        (manager_token, "manager@example.com", "manager"),
        (staff_token, "staff@example.com", "staff"),
        (viewer_token, "viewer@example.com", "viewer"),
    ]:
        await invite_and_accept(rbac_client, owner_token, token, organization_id, email, role)

    manager_create = await rbac_client.post(
        "/api/v1/branches",
        headers=auth(manager_token),
        json={"name": "Managed Branch", "slug": "managed"},
    )
    assert manager_create.status_code == 201
    branch_id = manager_create.json()["id"]

    staff_update = await rbac_client.patch(
        f"/api/v1/branches/{branch_id}",
        headers=auth(staff_token),
        json={"name": "Staff Updated"},
    )
    staff_create = await rbac_client.post(
        "/api/v1/branches",
        headers=auth(staff_token),
        json={"name": "Not Allowed", "slug": "not-allowed"},
    )
    viewer_read = await rbac_client.get(f"/api/v1/branches/{branch_id}", headers=auth(viewer_token))
    viewer_update = await rbac_client.patch(
        f"/api/v1/branches/{branch_id}",
        headers=auth(viewer_token),
        json={"name": "Escalated"},
    )
    assert staff_update.status_code == 200
    assert staff_create.status_code == 403
    assert viewer_read.status_code == 200
    assert viewer_update.status_code == 403

    assert (
        await rbac_client.get("/api/v1/members", headers=auth(manager_token))
    ).status_code == 200
    assert (
        await rbac_client.get("/api/v1/audit-events", headers=auth(manager_token))
    ).status_code == 200
    assert (await rbac_client.get("/api/v1/members", headers=auth(viewer_token))).status_code == 403
    assert (
        await rbac_client.get("/api/v1/audit-events", headers=auth(viewer_token))
    ).status_code == 403

    admin_self_promote = await rbac_client.patch(
        f"/api/v1/members/{admin_id}/role",
        headers=auth(admin_token),
        json={"role": "owner"},
    )
    admin_promote_staff = await rbac_client.patch(
        f"/api/v1/members/{staff_id}/role",
        headers=auth(admin_token),
        json={"role": "admin"},
    )
    admin_manage_viewer = await rbac_client.patch(
        f"/api/v1/members/{viewer_id}/role",
        headers=auth(admin_token),
        json={"role": "staff"},
    )
    manager_manage_role = await rbac_client.patch(
        f"/api/v1/members/{staff_id}/role",
        headers=auth(manager_token),
        json={"role": "viewer"},
    )
    assert admin_self_promote.status_code == 403
    assert admin_promote_staff.status_code == 403
    assert admin_manage_viewer.status_code == 200
    assert manager_manage_role.status_code == 403

    removed = await rbac_client.delete(f"/api/v1/members/{manager_id}", headers=auth(admin_token))
    assert removed.status_code == 204
    assert (
        await rbac_client.get("/api/v1/branches", headers=auth(manager_token))
    ).status_code == 409


async def test_last_active_owner_is_protected(rbac_client: AsyncClient) -> None:
    owner_token, owner_id = await register(rbac_client, "last-owner@example.com")
    second_token, second_id = await register(rbac_client, "second-owner@example.com")
    organization_id = await create_organization(rbac_client, owner_token, "owner-protection")

    demote_last = await rbac_client.patch(
        f"/api/v1/members/{owner_id}/role",
        headers=auth(owner_token),
        json={"role": "admin"},
    )
    remove_last = await rbac_client.delete(f"/api/v1/members/{owner_id}", headers=auth(owner_token))
    assert demote_last.status_code == remove_last.status_code == 409
    assert demote_last.json()["error"]["code"] == "last_owner_protected"

    await invite_and_accept(
        rbac_client,
        owner_token,
        second_token,
        organization_id,
        "second-owner@example.com",
        "viewer",
    )
    promoted = await rbac_client.patch(
        f"/api/v1/members/{second_id}/role",
        headers=auth(owner_token),
        json={"role": "owner"},
    )
    demoted = await rbac_client.patch(
        f"/api/v1/members/{owner_id}/role",
        headers=auth(owner_token),
        json={"role": "admin"},
    )
    assert promoted.status_code == demoted.status_code == 200
    assert (
        await rbac_client.delete(f"/api/v1/members/{second_id}", headers=auth(second_token))
    ).status_code == 409


async def test_role_management_and_audit_are_tenant_scoped(rbac_client: AsyncClient) -> None:
    alice_token, _ = await register(rbac_client, "alice-rbac@example.com")
    bob_token, bob_id = await register(rbac_client, "bob-rbac@example.com")
    alice_org = await create_organization(rbac_client, alice_token, "alice-rbac")
    bob_org = await create_organization(rbac_client, bob_token, "bob-rbac")

    cross_role = await rbac_client.patch(
        f"/api/v1/members/{bob_id}/role",
        headers=auth(alice_token),
        json={"role": "viewer"},
    )
    cross_remove = await rbac_client.delete(f"/api/v1/members/{bob_id}", headers=auth(alice_token))
    assert cross_role.status_code == cross_remove.status_code == 404

    audit = await rbac_client.get("/api/v1/audit-events", headers=auth(alice_token))
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    assert audit.json()["items"][0]["target_id"] == alice_org
    assert bob_org not in audit.text


async def test_audit_events_are_immutable_in_api_and_database(
    rbac_client: AsyncClient, rbac_database_url: str
) -> None:
    owner_token, _ = await register(rbac_client, "audit-owner@example.com")
    await create_organization(rbac_client, owner_token, "immutable-audit")
    audit = await rbac_client.get("/api/v1/audit-events", headers=auth(owner_token))
    event_id = audit.json()["items"][0]["id"]

    api_update = await rbac_client.patch(
        "/api/v1/audit-events", headers=auth(owner_token), json={"details": {}}
    )
    api_delete = await rbac_client.delete("/api/v1/audit-events", headers=auth(owner_token))
    assert api_update.status_code == api_delete.status_code == 405

    manager = DatabaseManager(rbac_database_url, 3)
    with pytest.raises(DBAPIError, match="audit events are immutable"):
        async with manager.transaction() as session:
            await session.execute(
                update(OrganizationAuditEvent)
                .where(OrganizationAuditEvent.id == event_id)
                .values(event_type="tampered")
            )
    with pytest.raises(DBAPIError, match="audit events are immutable"):
        async with manager.transaction() as session:
            await session.execute(
                delete(OrganizationAuditEvent).where(OrganizationAuditEvent.id == event_id)
            )
    await manager.dispose()
