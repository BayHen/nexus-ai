"""Create tenant-scoped knowledge documents and pgvector chunks.

Revision ID: 20261031_0012
Revises: 20261031_0011
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261031_0012"
down_revision: str | None = "20261031_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="ready", nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "visibility IN ('organization', 'private')",
            name="ck_knowledge_documents_valid_visibility",
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'failed')", name="ck_knowledge_documents_valid_status"
        ),
        sa.CheckConstraint("file_size > 0", name="ck_knowledge_documents_positive_file_size"),
        sa.CheckConstraint(
            "chunk_count >= 0", name="ck_knowledge_documents_non_negative_chunk_count"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["auth_users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_documents")),
        sa.UniqueConstraint("organization_id", "id", name="uq_knowledge_document_org_id"),
    )
    op.create_index(
        "ix_knowledge_documents_org_created",
        "knowledge_documents",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_knowledge_documents_org_visibility",
        "knowledge_documents",
        ["organization_id", "visibility"],
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["knowledge_documents.organization_id", "knowledge_documents.id"],
            name="fk_knowledge_chunk_org_document",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_chunks")),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_knowledge_chunk_ordinal"),
    )
    op.create_index(
        "ix_knowledge_chunks_org_document",
        "knowledge_chunks",
        ["organization_id", "document_id"],
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding_hnsw ON knowledge_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_knowledge_chunks_embedding_hnsw")
    op.drop_index("ix_knowledge_chunks_org_document", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_documents_org_visibility", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_org_created", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
