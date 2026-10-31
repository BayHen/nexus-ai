"""Create business agent run and immutable tool invocation audit records.

Revision ID: 20261031_0013
Revises: 20261031_0012
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261031_0013"
down_revision: str | None = "20261031_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), server_default="running", nullable=False),
        sa.Column("selected_tool", sa.String(64), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("transition_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'denied', 'unsupported')",
            name="ck_agent_runs_status",
        ),
        sa.CheckConstraint("transition_count >= 0", name="ck_agent_runs_transition_count"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index("ix_agent_runs_org_created", "agent_runs", ["organization_id", "created_at"])
    op.create_table(
        "agent_tool_invocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("input_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("output_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed', 'denied')",
            name="ck_agent_tool_invocations_status",
        ),
        sa.CheckConstraint("duration_ms >= 0", name="ck_agent_tool_invocations_duration"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_tool_invocations")),
    )
    op.create_index(
        "ix_agent_tool_invocations_run_created",
        "agent_tool_invocations",
        ["run_id", "created_at"],
    )
    op.create_index(
        "ix_agent_tool_invocations_org_tool",
        "agent_tool_invocations",
        ["organization_id", "tool_name"],
    )
    op.execute(
        "CREATE TRIGGER agent_tool_invocations_immutable "
        "BEFORE UPDATE OR DELETE ON agent_tool_invocations "
        "FOR EACH ROW EXECUTE FUNCTION reject_reliability_history_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER agent_tool_invocations_immutable ON agent_tool_invocations")
    op.drop_index("ix_agent_tool_invocations_org_tool", table_name="agent_tool_invocations")
    op.drop_index("ix_agent_tool_invocations_run_created", table_name="agent_tool_invocations")
    op.drop_table("agent_tool_invocations")
    op.drop_index("ix_agent_runs_org_created", table_name="agent_runs")
    op.drop_table("agent_runs")
