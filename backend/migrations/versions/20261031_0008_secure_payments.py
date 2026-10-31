"""Create sandbox payments, refunds, webhook deduplication, and audit history.

Revision ID: 20261031_0008
Revises: 20261030_0007
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261031_0008"
down_revision: str | None = "20261030_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_orders_valid_status", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_valid_status",
        "orders",
        "status IN ('draft', 'confirmed', 'completed', 'cancelled')",
    )
    op.create_table(
        "payment_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_intent_id", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'refunded')",
            name="ck_payment_intents_valid_status",
        ),
        sa.CheckConstraint("amount > 0", name="ck_payment_intents_positive_amount"),
        sa.ForeignKeyConstraint(
            ["organization_id", "order_id"],
            ["orders.organization_id", "orders.id"],
            name="fk_payment_intent_org_order",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["auth_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_intents")),
        sa.UniqueConstraint("organization_id", "id", name="uq_payment_intents_org_id"),
        sa.UniqueConstraint("organization_id", "order_id", name="uq_payment_intents_org_order"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_payment_intents_idem"),
        sa.UniqueConstraint("provider", "provider_intent_id", name="uq_provider_payment_intent"),
    )
    op.create_index(
        "ix_payment_intents_org_status_created",
        "payment_intents",
        ["organization_id", "status", "created_at"],
    )
    op.create_table(
        "payment_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_refund_id", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_payment_refunds_valid_status",
        ),
        sa.CheckConstraint("amount > 0", name="ck_payment_refunds_positive_amount"),
        sa.ForeignKeyConstraint(
            ["organization_id", "payment_id"],
            ["payment_intents.organization_id", "payment_intents.id"],
            name="fk_payment_refund_org_payment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["auth_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_refunds")),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_payment_refunds_idem"),
        sa.UniqueConstraint("provider_refund_id", name="uq_provider_refund"),
    )
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("refund_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_intents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["refund_id"], ["payment_refunds.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_webhook_events")),
        sa.UniqueConstraint("provider", "event_id", name="uq_payment_webhook_event"),
    )
    op.create_table(
        "payment_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("previous_status", sa.String(16), nullable=True),
        sa.Column("new_status", sa.String(16), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "details", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_intents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["auth_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_audit_logs")),
    )
    op.create_index(
        "ix_payment_audit_org_created", "payment_audit_logs", ["organization_id", "created_at"]
    )
    op.execute(
        """
        CREATE FUNCTION reject_financial_record_delete()
        RETURNS trigger AS $$ BEGIN
            RAISE EXCEPTION 'financial records cannot be deleted';
        END; $$ LANGUAGE plpgsql
        """
    )
    for table in ("payment_intents", "payment_refunds"):
        op.execute(
            f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_financial_record_delete()"
        )
    op.execute(
        """
        CREATE FUNCTION reject_payment_history_mutation()
        RETURNS trigger AS $$ BEGIN
            RAISE EXCEPTION 'payment history is immutable';
        END; $$ LANGUAGE plpgsql
        """
    )
    for table in ("payment_webhook_events", "payment_audit_logs"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_payment_history_mutation()"
        )


def downgrade() -> None:
    for table in ("payment_webhook_events", "payment_audit_logs"):
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
    op.execute("DROP FUNCTION reject_payment_history_mutation()")
    for table in ("payment_intents", "payment_refunds"):
        op.execute(f"DROP TRIGGER {table}_no_delete ON {table}")
    op.execute("DROP FUNCTION reject_financial_record_delete()")
    op.drop_index("ix_payment_audit_org_created", table_name="payment_audit_logs")
    op.drop_table("payment_audit_logs")
    op.drop_table("payment_webhook_events")
    op.drop_table("payment_refunds")
    op.drop_index("ix_payment_intents_org_status_created", table_name="payment_intents")
    op.drop_table("payment_intents")
    op.drop_constraint("ck_orders_valid_status", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_valid_status", "orders", "status IN ('draft', 'confirmed', 'cancelled')"
    )
