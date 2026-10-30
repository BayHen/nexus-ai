"""Create transaction-safe inventory state and immutable movement ledger.

Revision ID: 20261030_0006
Revises: 20261030_0005
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261030_0006"
down_revision: str | None = "20261030_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_catalog_products_org_id", "catalog_products", ["organization_id", "id"]
    )
    op.create_table(
        "inventory_policies",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allow_negative_stock", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organization_id", name=op.f("pk_inventory_policies")),
    )
    op.create_table(
        "inventory_stock_levels",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(19, 4), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "low_stock_threshold",
            sa.Numeric(19, 4),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "low_stock_threshold >= 0",
            name=op.f("ck_inventory_stock_levels_non_negative_threshold"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "branch_id"],
            ["organization_branches.organization_id", "organization_branches.id"],
            name="fk_inventory_stock_org_branch",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["catalog_products.organization_id", "catalog_products.id"],
            name="fk_inventory_stock_org_product",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "branch_id", "product_id", name=op.f("pk_inventory_stock_levels")
        ),
    )
    op.create_index(
        "ix_inventory_stock_org_product",
        "inventory_stock_levels",
        ["organization_id", "product_id"],
    )
    op.create_table(
        "inventory_stock_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("destination_branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("movement_type", sa.String(16), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(19, 4), nullable=False),
        sa.Column("source_quantity_after", sa.Numeric(19, 4), nullable=True),
        sa.Column("destination_quantity_after", sa.Numeric(19, 4), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("reference", sa.String(160), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "movement_type IN ('adjustment', 'transfer')",
            name=op.f("ck_inventory_stock_movements_valid_type"),
        ),
        sa.CheckConstraint(
            "quantity_delta <> 0", name=op.f("ck_inventory_stock_movements_non_zero_quantity")
        ),
        sa.CheckConstraint(
            "movement_type = 'adjustment' OR quantity_delta > 0",
            name=op.f("ck_inventory_stock_movements_positive_transfer"),
        ),
        sa.CheckConstraint(
            "(movement_type = 'adjustment' AND source_branch_id IS NULL "
            "AND destination_branch_id IS NOT NULL) OR "
            "(movement_type = 'transfer' AND source_branch_id IS NOT NULL "
            "AND destination_branch_id IS NOT NULL AND source_branch_id <> destination_branch_id)",
            name=op.f("ck_inventory_stock_movements_valid_branches"),
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["auth_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["catalog_products.organization_id", "catalog_products.id"],
            name="fk_inventory_movement_org_product",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "source_branch_id"],
            ["organization_branches.organization_id", "organization_branches.id"],
            name="fk_inventory_movement_org_source_branch",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "destination_branch_id"],
            ["organization_branches.organization_id", "organization_branches.id"],
            name="fk_inventory_movement_org_destination_branch",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_stock_movements")),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_inventory_movement_idem"
        ),
    )
    op.create_index(
        "ix_inventory_movement_org_created",
        "inventory_stock_movements",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_inventory_movement_org_product",
        "inventory_stock_movements",
        ["organization_id", "product_id"],
    )
    op.execute(
        """
        CREATE FUNCTION enforce_inventory_negative_stock_policy()
        RETURNS trigger AS $$
        DECLARE policy_allows boolean;
        BEGIN
            SELECT allow_negative_stock INTO policy_allows
            FROM inventory_policies WHERE organization_id = NEW.organization_id;
            IF NEW.quantity < 0 AND NOT COALESCE(policy_allows, false) THEN
                RAISE EXCEPTION 'negative inventory is disabled';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER inventory_negative_stock_policy
        BEFORE INSERT OR UPDATE OF quantity ON inventory_stock_levels
        FOR EACH ROW EXECUTE FUNCTION enforce_inventory_negative_stock_policy()
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_inventory_movement_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'inventory movements are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER inventory_movements_immutable
        BEFORE UPDATE OR DELETE ON inventory_stock_movements
        FOR EACH ROW EXECUTE FUNCTION reject_inventory_movement_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER inventory_movements_immutable ON inventory_stock_movements")
    op.execute("DROP FUNCTION reject_inventory_movement_mutation()")
    op.execute("DROP TRIGGER inventory_negative_stock_policy ON inventory_stock_levels")
    op.execute("DROP FUNCTION enforce_inventory_negative_stock_policy()")
    op.drop_index("ix_inventory_movement_org_product", table_name="inventory_stock_movements")
    op.drop_index("ix_inventory_movement_org_created", table_name="inventory_stock_movements")
    op.drop_table("inventory_stock_movements")
    op.drop_index("ix_inventory_stock_org_product", table_name="inventory_stock_levels")
    op.drop_table("inventory_stock_levels")
    op.drop_table("inventory_policies")
    op.drop_constraint("uq_catalog_products_org_id", "catalog_products", type_="unique")
