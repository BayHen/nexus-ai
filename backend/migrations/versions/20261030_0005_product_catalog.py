"""Create tenant-scoped categories, products, and SKU counters.

Revision ID: 20261030_0005
Revises: 20261030_0004
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261030_0005"
down_revision: str | None = "20261030_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_catalog_categories_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_categories")),
        sa.UniqueConstraint("organization_id", "id", name="uq_catalog_categories_org_id"),
    )
    op.create_index(
        "uq_catalog_categories_org_name_active",
        "catalog_categories",
        ["organization_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_catalog_categories_org_slug_active",
        "catalog_categories",
        ["organization_id", "slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "catalog_sku_counters",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("next_value", sa.Integer(), nullable=False),
        sa.CheckConstraint("next_value > 0", name="ck_catalog_sku_counters_positive_value"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_catalog_sku_counters_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organization_id", name=op.f("pk_catalog_sku_counters")),
    )

    op.create_table(
        "catalog_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sku", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("price >= 0", name=op.f("ck_catalog_products_non_negative_price")),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name=op.f("ck_catalog_products_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "category_id"],
            ["catalog_categories.organization_id", "catalog_categories.id"],
            name="fk_catalog_products_org_category",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_catalog_products_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_products")),
        sa.UniqueConstraint("organization_id", "sku", name="uq_catalog_products_org_sku"),
    )
    op.create_index(
        "ix_catalog_products_org_category",
        "catalog_products",
        ["organization_id", "category_id"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_products_org_name",
        "catalog_products",
        ["organization_id", "name"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_products_org_status",
        "catalog_products",
        ["organization_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_products_org_status", table_name="catalog_products")
    op.drop_index("ix_catalog_products_org_name", table_name="catalog_products")
    op.drop_index("ix_catalog_products_org_category", table_name="catalog_products")
    op.drop_table("catalog_products")
    op.drop_table("catalog_sku_counters")
    op.drop_index("uq_catalog_categories_org_slug_active", table_name="catalog_categories")
    op.drop_index("uq_catalog_categories_org_name_active", table_name="catalog_categories")
    op.drop_table("catalog_categories")
