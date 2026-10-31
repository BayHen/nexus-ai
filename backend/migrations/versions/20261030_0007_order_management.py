"""Create tenant-scoped orders and immutable item price snapshots.

Revision ID: 20261030_0007
Revises: 20261030_0006
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261030_0007"
down_revision: str | None = "20261030_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("total_amount", sa.Numeric(19, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'cancelled')", name="ck_orders_valid_status"
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_orders_non_negative_total"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["auth_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("organization_id", "id", name="uq_orders_org_id"),
    )
    op.create_index(
        "ix_orders_org_status_created", "orders", ["organization_id", "status", "created_at"]
    )
    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_sku_snapshot", sa.String(32), nullable=False),
        sa.Column("product_name_snapshot", sa.String(200), nullable=False),
        sa.Column("unit_price_snapshot", sa.Numeric(19, 4), nullable=False),
        sa.Column("quantity", sa.Numeric(19, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(19, 4), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_positive_quantity"),
        sa.CheckConstraint("unit_price_snapshot >= 0", name="ck_order_items_non_negative_price"),
        sa.CheckConstraint("line_total >= 0", name="ck_order_items_non_negative_line_total"),
        sa.CheckConstraint(
            "line_total = unit_price_snapshot * quantity", name="ck_order_items_exact_line_total"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "order_id"],
            ["orders.organization_id", "orders.id"],
            name="fk_order_item_org_order",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["catalog_products.organization_id", "catalog_products.id"],
            name="fk_order_item_org_product",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "branch_id"],
            ["organization_branches.organization_id", "organization_branches.id"],
            name="fk_order_item_org_branch",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.UniqueConstraint(
            "organization_id", "order_id", "branch_id", "product_id", name="uq_order_item_stock"
        ),
    )
    op.create_index("ix_order_items_org_order", "order_items", ["organization_id", "order_id"])
    op.execute(
        """
        CREATE FUNCTION reject_order_item_snapshot_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.product_id IS DISTINCT FROM OLD.product_id
               OR NEW.branch_id IS DISTINCT FROM OLD.branch_id
               OR NEW.product_sku_snapshot IS DISTINCT FROM OLD.product_sku_snapshot
               OR NEW.product_name_snapshot IS DISTINCT FROM OLD.product_name_snapshot
               OR NEW.unit_price_snapshot IS DISTINCT FROM OLD.unit_price_snapshot THEN
                RAISE EXCEPTION 'order item snapshots are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER order_item_snapshots_immutable
        BEFORE UPDATE ON order_items
        FOR EACH ROW EXECUTE FUNCTION reject_order_item_snapshot_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER order_item_snapshots_immutable ON order_items")
    op.execute("DROP FUNCTION reject_order_item_snapshot_mutation()")
    op.drop_index("ix_order_items_org_order", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_org_status_created", table_name="orders")
    op.drop_table("orders")
