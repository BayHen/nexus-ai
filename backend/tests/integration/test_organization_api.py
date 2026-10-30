"""Cross-tenant organization API security tests against PostgreSQL."""

from collections.abc import AsyncIterator

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings
from nexus.platform.database.manager import DatabaseManager
from tests.integration.test_migrations import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PASSWORD = "correct horse battery staple"


@pytest.fixture
def organization_database_url(temporary_database_url: str) -> str:
    command.upgrade(alembic_config(temporary_database_url), "head")
    return temporary_database_url


@pytest.fixture
async def organization_client(organization_database_url: str) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment="test",
        database_url=organization_database_url,
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        _env_file=None,
    )
    manager = DatabaseManager(organization_database_url, 3)
    app = create_app(settings, manager)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await manager.dispose()


async def register(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["tokens"]["access_token"])


def auth(token: str, **headers: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", **headers}


async def create_organization(client: AsyncClient, token: str, name: str, slug: str) -> str:
    response = await client.post(
        "/api/v1/organizations",
        headers=auth(token),
        json={"name": name, "slug": slug},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def create_branch(client: AsyncClient, token: str, name: str, slug: str) -> str:
    response = await client.post(
        "/api/v1/branches",
        headers=auth(token),
        json={"name": name, "slug": slug},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def test_malicious_cross_tenant_ids_cannot_read_modify_or_activate(
    organization_client: AsyncClient,
) -> None:
    alice_token = await register(organization_client, "alice@example.com")
    bob_token = await register(organization_client, "bob@example.com")
    alice_org = await create_organization(
        organization_client, alice_token, "Alice Org", "alice-org"
    )
    alice_branch = await create_branch(
        organization_client, alice_token, "Alice Branch", "alice-branch"
    )
    bob_org = await create_organization(organization_client, bob_token, "Bob Org", "bob-org")
    bob_branch = await create_branch(organization_client, bob_token, "Bob Branch", "bob-branch")

    read_other = await organization_client.get(
        f"/api/v1/branches/{bob_branch}", headers=auth(alice_token)
    )
    modify_other = await organization_client.patch(
        f"/api/v1/branches/{bob_branch}",
        headers=auth(alice_token),
        json={"name": "Compromised"},
    )
    activate_other = await organization_client.post(
        f"/api/v1/organizations/{bob_org}/activate", headers=auth(alice_token)
    )
    assert read_other.status_code == modify_other.status_code == activate_other.status_code == 404

    spoofed = await organization_client.get(
        f"/api/v1/branches?organization_id={bob_org}",
        headers=auth(alice_token, **{"X-Organization-ID": bob_org}),
    )
    assert spoofed.status_code == 200
    assert [item["id"] for item in spoofed.json()["items"]] == [alice_branch]
    assert bob_branch not in spoofed.text

    alice_organizations = await organization_client.get(
        "/api/v1/organizations", headers=auth(alice_token)
    )
    assert alice_organizations.json()["total"] == 1
    assert alice_organizations.json()["items"][0]["id"] == alice_org


async def test_invitation_is_pending_until_acceptance_and_supports_multiple_orgs(
    organization_client: AsyncClient,
) -> None:
    owner_token = await register(organization_client, "owner@example.com")
    member_token = await register(organization_client, "member@example.com")
    owner_org = await create_organization(
        organization_client, owner_token, "Owner Workspace", "owner-workspace"
    )
    member_org = await create_organization(
        organization_client, member_token, "Member Workspace", "member-workspace"
    )
    await create_branch(organization_client, owner_token, "Private Branch", "private")

    invitation = await organization_client.post(
        "/api/v1/organizations/current/invitations",
        headers=auth(owner_token),
        json={"email": "member@example.com", "role": "viewer"},
    )
    assert invitation.status_code == 201
    assert invitation.json()["status"] == "pending"

    pending_activation = await organization_client.post(
        f"/api/v1/organizations/{owner_org}/activate", headers=auth(member_token)
    )
    assert pending_activation.status_code == 404

    accepted = await organization_client.post(
        f"/api/v1/organizations/{owner_org}/invitations/accept",
        headers=auth(member_token),
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "active"

    organizations = await organization_client.get(
        "/api/v1/organizations?query=Workspace&page=1&page_size=1",
        headers=auth(member_token),
    )
    assert organizations.status_code == 200
    assert organizations.json()["total"] == 2
    assert len(organizations.json()["items"]) == 1

    member_write = await organization_client.post(
        "/api/v1/branches",
        headers=auth(member_token),
        json={"name": "Unauthorized", "slug": "unauthorized"},
    )
    assert member_write.status_code == 403

    activated = await organization_client.post(
        f"/api/v1/organizations/{member_org}/activate", headers=auth(member_token)
    )
    assert activated.status_code == 200
    own_branches = await organization_client.get("/api/v1/branches", headers=auth(member_token))
    assert own_branches.status_code == 200
    assert own_branches.json()["total"] == 0


async def test_business_api_requires_server_side_active_tenant(
    organization_client: AsyncClient,
) -> None:
    token = await register(organization_client, "no-tenant@example.com")
    response = await organization_client.get("/api/v1/branches", headers=auth(token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "tenant_context_required"


async def test_branch_pagination_and_filters_are_tenant_scoped(
    organization_client: AsyncClient,
) -> None:
    token = await register(organization_client, "filter@example.com")
    await create_organization(organization_client, token, "Filter Org", "filter-org")
    first_id = await create_branch(organization_client, token, "Alpha North", "alpha-north")
    second_id = await create_branch(organization_client, token, "Alpha South", "alpha-south")
    await create_branch(organization_client, token, "Beta", "beta")
    await organization_client.patch(
        f"/api/v1/branches/{second_id}",
        headers=auth(token),
        json={"is_active": False},
    )

    response = await organization_client.get(
        "/api/v1/branches?query=Alpha&is_active=true&page=1&page_size=1",
        headers=auth(token),
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [first_id]
