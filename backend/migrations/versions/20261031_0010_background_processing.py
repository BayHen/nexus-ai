"""Create durable background jobs and immutable outputs.

Revision ID: 20261031_0010
Revises: 20261031_0009
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261031_0010"
down_revision: str | None = "20261031_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_name", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), server_default="queued", nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'retrying', 'succeeded', 'failed', 'dead')",
            name="ck_background_jobs_valid_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ck_background_jobs_non_negative_attempts"
        ),
        sa.CheckConstraint("max_attempts > 0", name="ck_background_jobs_positive_max_attempts"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_background_jobs")),
        sa.UniqueConstraint(
            "organization_id", "task_name", "idempotency_key", name="uq_background_job_idem"
        ),
    )
    op.create_index(
        "ix_background_jobs_org_created", "background_jobs", ["organization_id", "created_at"]
    )
    op.create_index(
        "ix_background_jobs_status_updated", "background_jobs", ["status", "updated_at"]
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("provider_message_id", sa.String(128), nullable=False),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["background_jobs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_deliveries")),
        sa.UniqueConstraint("job_id", name="uq_notification_delivery_job"),
    )
    op.create_table(
        "business_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_type", sa.String(64), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["background_jobs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_business_reports")),
        sa.UniqueConstraint("job_id", name="uq_business_report_job"),
    )
    op.create_table(
        "low_stock_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.String(32), nullable=False),
        sa.Column("threshold", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["background_jobs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_low_stock_alerts")),
        sa.UniqueConstraint(
            "job_id", "branch_id", "product_id", name="uq_low_stock_alert_job_item"
        ),
    )
    op.create_index(
        "ix_low_stock_alerts_org_created", "low_stock_alerts", ["organization_id", "created_at"]
    )
    for table in ("notification_deliveries", "business_reports", "low_stock_alerts"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_reliability_history_mutation()"
        )


def downgrade() -> None:
    for table in ("notification_deliveries", "business_reports", "low_stock_alerts"):
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
    op.drop_index("ix_low_stock_alerts_org_created", table_name="low_stock_alerts")
    op.drop_table("low_stock_alerts")
    op.drop_table("business_reports")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_background_jobs_status_updated", table_name="background_jobs")
    op.drop_index("ix_background_jobs_org_created", table_name="background_jobs")
    op.drop_table("background_jobs")
