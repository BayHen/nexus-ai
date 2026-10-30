"""Expand tenant roles and add immutable authorization audit events.

Revision ID: 20261030_0004
Revises: 20261030_0003
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261030_0004"
down_revision: str | None = "20261030_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_organization_memberships_valid_role"),
        "organization_memberships",
        type_="check",
    )
    op.execute("UPDATE organization_memberships SET role = 'viewer' WHERE role = 'member'")
    op.create_check_constraint(
        op.f("ck_organization_memberships_valid_role"),
        "organization_memberships",
        "role IN ('owner', 'admin', 'manager', 'staff', 'viewer')",
    )

    op.create_table(
        "organization_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["auth_users.id"],
            name=op.f("fk_organization_audit_events_actor_user_id_auth_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_audit_events_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_audit_events")),
    )
    op.create_index(
        "ix_org_audit_events_org_created",
        "organization_audit_events",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_org_audit_events_org_type",
        "organization_audit_events",
        ["organization_id", "event_type"],
        unique=False,
    )
    op.execute(
        """
        CREATE FUNCTION reject_organization_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'organization audit events are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER organization_audit_events_immutable
        BEFORE UPDATE OR DELETE ON organization_audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_organization_audit_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER organization_audit_events_immutable ON organization_audit_events")
    op.execute("DROP FUNCTION reject_organization_audit_mutation()")
    op.drop_index("ix_org_audit_events_org_type", table_name="organization_audit_events")
    op.drop_index("ix_org_audit_events_org_created", table_name="organization_audit_events")
    op.drop_table("organization_audit_events")

    op.drop_constraint(
        op.f("ck_organization_memberships_valid_role"),
        "organization_memberships",
        type_="check",
    )
    op.execute(
        "UPDATE organization_memberships SET role = 'member' "
        "WHERE role IN ('manager', 'staff', 'viewer')"
    )
    op.create_check_constraint(
        op.f("ck_organization_memberships_valid_role"),
        "organization_memberships",
        "role IN ('owner', 'admin', 'member')",
    )
