"""Create authentication identities and revocable token state.

Revision ID: 20261030_0002
Revises: 20261030_0001
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261030_0002"
down_revision: str | None = "20261030_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_users")),
        sa.UniqueConstraint("email", name=op.f("uq_auth_users_email")),
    )
    op.create_index(op.f("ix_auth_users_email"), "auth_users", ["email"], unique=False)
    op.create_table(
        "auth_refresh_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["auth_refresh_sessions.id"],
            name=op.f("fk_auth_refresh_sessions_replaced_by_id_auth_refresh_sessions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_users.id"],
            name=op.f("fk_auth_refresh_sessions_user_id_auth_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_refresh_sessions")),
    )
    op.create_index(
        "ix_auth_refresh_sessions_user_active",
        "auth_refresh_sessions",
        ["user_id", "revoked_at"],
        unique=False,
    )
    op.create_table(
        "auth_password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_users.id"],
            name=op.f("fk_auth_password_reset_tokens_user_id_auth_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_password_reset_tokens")),
        sa.UniqueConstraint(
            "token_digest", name=op.f("uq_auth_password_reset_tokens_token_digest")
        ),
    )
    op.create_index(
        "ix_auth_password_reset_user_active",
        "auth_password_reset_tokens",
        ["user_id", "used_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_password_reset_user_active", table_name="auth_password_reset_tokens")
    op.drop_table("auth_password_reset_tokens")
    op.drop_index("ix_auth_refresh_sessions_user_active", table_name="auth_refresh_sessions")
    op.drop_table("auth_refresh_sessions")
    op.drop_index(op.f("ix_auth_users_email"), table_name="auth_users")
    op.drop_table("auth_users")
