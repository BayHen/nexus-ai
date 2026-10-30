"""SQLAlchemy mappings for stock state and immutable movement history."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from nexus.platform.database.base import Base


class InventoryPolicy(Base):
    """Server-owned organization policy for negative stock."""

    __tablename__ = "inventory_policies"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    allow_negative_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class StockLevel(Base):
    """Current on-hand quantity for one product at one branch."""

    __tablename__ = "inventory_stock_levels"
    __table_args__ = (
        PrimaryKeyConstraint("organization_id", "branch_id", "product_id"),
        CheckConstraint("low_stock_threshold >= 0", name="non_negative_threshold"),
        ForeignKeyConstraint(
            ["organization_id", "branch_id"],
            ["organization_branches.organization_id", "organization_branches.id"],
            name="fk_inventory_stock_org_branch",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["catalog_products.organization_id", "catalog_products.id"],
            name="fk_inventory_stock_org_product",
            ondelete="RESTRICT",
        ),
        Index("ix_inventory_stock_org_product", "organization_id", "product_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=Decimal("0"))
    low_stock_threshold: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class StockMovement(Base):
    """Immutable adjustment or transfer with quantity snapshots."""

    __tablename__ = "inventory_stock_movements"
    __table_args__ = (
        CheckConstraint("movement_type IN ('adjustment', 'transfer')", name="valid_type"),
        CheckConstraint("quantity_delta <> 0", name="non_zero_quantity"),
        CheckConstraint(
            "movement_type = 'adjustment' OR quantity_delta > 0", name="positive_transfer"
        ),
        CheckConstraint(
            "(movement_type = 'adjustment' AND source_branch_id IS NULL "
            "AND destination_branch_id IS NOT NULL) OR "
            "(movement_type = 'transfer' AND source_branch_id IS NOT NULL "
            "AND destination_branch_id IS NOT NULL AND source_branch_id <> destination_branch_id)",
            name="valid_branches",
        ),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_inventory_movement_idem"),
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["catalog_products.organization_id", "catalog_products.id"],
            name="fk_inventory_movement_org_product",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_branch_id"],
            ["organization_branches.organization_id", "organization_branches.id"],
            name="fk_inventory_movement_org_source_branch",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "destination_branch_id"],
            ["organization_branches.organization_id", "organization_branches.id"],
            name="fk_inventory_movement_org_destination_branch",
            ondelete="RESTRICT",
        ),
        Index("ix_inventory_movement_org_created", "organization_id", "created_at"),
        Index("ix_inventory_movement_org_product", "organization_id", "product_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_branch_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    destination_branch_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    source_quantity_after: Mapped[Decimal | None] = mapped_column(Numeric(19, 4))
    destination_quantity_after: Mapped[Decimal | None] = mapped_column(Numeric(19, 4))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(160))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
