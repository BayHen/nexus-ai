"""Create analytics exports and indexes for reporting queries.

Revision ID: 20261031_0011
Revises: 20261031_0010
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261031_0011"
down_revision: str | None = "20261031_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_payment_intents_analytics",
        "payment_intents",
        ["organization_id", "currency", "status", "succeeded_at", "order_id"],
    )
    op.create_index(
        "ix_payment_refunds_org_status_payment",
        "payment_refunds",
        ["organization_id", "status", "payment_id"],
    )
    op.create_index(
        "ix_order_items_org_branch_order",
        "order_items",
        ["organization_id", "branch_id", "order_id"],
    )
    op.create_table(
        "analytics_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_format", sa.String(8), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["job_id"], ["background_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analytics_exports")),
        sa.UniqueConstraint("job_id", name="uq_analytics_export_job"),
    )
    op.create_index(
        "ix_analytics_exports_org_created",
        "analytics_exports",
        ["organization_id", "created_at"],
    )
    op.execute(
        "CREATE TRIGGER analytics_exports_immutable BEFORE UPDATE OR DELETE ON analytics_exports "
        "FOR EACH ROW EXECUTE FUNCTION reject_reliability_history_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER analytics_exports_immutable ON analytics_exports")
    op.drop_index("ix_analytics_exports_org_created", table_name="analytics_exports")
    op.drop_table("analytics_exports")
    op.drop_index("ix_order_items_org_branch_order", table_name="order_items")
    op.drop_index("ix_payment_refunds_org_status_payment", table_name="payment_refunds")
    op.drop_index("ix_payment_intents_analytics", table_name="payment_intents")
