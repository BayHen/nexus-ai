"""Create transactional outbox, inbox receipts, audit, and reconciliation records.

Revision ID: 20261031_0009
Revises: 20261031_0008
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261031_0009"
down_revision: str | None = "20261031_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(32), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(128), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'published', 'dead')",
            name="ck_outbox_events_valid_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_outbox_events_non_negative_attempts"),
        sa.CheckConstraint("max_attempts > 0", name="ck_outbox_events_positive_max_attempts"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
    )
    op.create_index("ix_outbox_dispatch", "outbox_events", ["status", "available_at", "created_at"])
    op.create_index("ix_outbox_org_created", "outbox_events", ["organization_id", "created_at"])
    op.create_table(
        "inbox_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consumer_name", sa.String(80), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["event_id"], ["outbox_events.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inbox_receipts")),
        sa.UniqueConstraint("consumer_name", "event_id", name="uq_inbox_consumer_event"),
    )
    op.create_table(
        "business_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(32), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_business_audit_events")),
    )
    op.create_index(
        "ix_business_audit_org_created", "business_audit_events", ["organization_id", "created_at"]
    )
    op.create_index(
        "ix_business_audit_aggregate",
        "business_audit_events",
        ["organization_id", "aggregate_type", "aggregate_id"],
    )
    op.create_table(
        "reconciliation_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_code", sa.String(64), nullable=False),
        sa.Column("aggregate_type", sa.String(32), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column(
            "detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'resolved')", name="ck_reconciliation_findings_valid_status"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reconciliation_findings")),
        sa.UniqueConstraint(
            "organization_id", "finding_code", "aggregate_id", name="uq_reconciliation_finding"
        ),
    )
    op.create_index(
        "ix_reconciliation_org_status",
        "reconciliation_findings",
        ["organization_id", "status", "detected_at"],
    )
    op.execute(
        """
        CREATE FUNCTION reject_reliability_history_mutation()
        RETURNS trigger AS $$ BEGIN
            RAISE EXCEPTION 'reliability history is immutable';
        END; $$ LANGUAGE plpgsql
        """
    )
    for table in ("inbox_receipts", "business_audit_events"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_reliability_history_mutation()"
        )


def downgrade() -> None:
    for table in ("inbox_receipts", "business_audit_events"):
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
    op.execute("DROP FUNCTION reject_reliability_history_mutation()")
    op.drop_index("ix_reconciliation_org_status", table_name="reconciliation_findings")
    op.drop_table("reconciliation_findings")
    op.drop_index("ix_business_audit_aggregate", table_name="business_audit_events")
    op.drop_index("ix_business_audit_org_created", table_name="business_audit_events")
    op.drop_table("business_audit_events")
    op.drop_table("inbox_receipts")
    op.drop_index("ix_outbox_org_created", table_name="outbox_events")
    op.drop_index("ix_outbox_dispatch", table_name="outbox_events")
    op.drop_table("outbox_events")
