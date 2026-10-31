"""SQLAlchemy mappings for tenant-scoped orders and immutable price snapshots."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from nexus.platform.database.base import Base


class Order(Base):
    """Order aggregate root with a database-constrained state."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'confirmed', 'cancelled')", name="valid_status"),
        CheckConstraint("total_amount >= 0", name="non_negative_total"),
        UniqueConstraint("organization_id", "id", name="uq_orders_org_id"),
        Index("ix_orders_org_status_created", "organization_id", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OrderItem(Base):
    """Draft quantity plus an immutable server-captured Product price snapshot."""

    __tablename__ = "order_items"
    __table_args__ = (
        PrimaryKeyConstraint("id"),
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("unit_price_snapshot >= 0", name="non_negative_price"),
        CheckConstraint("line_total >= 0", name="non_negative_line_total"),
        CheckConstraint("line_total = unit_price_snapshot * quantity", name="exact_line_total"),
        UniqueConstraint(
            "organization_id", "order_id", "branch_id", "product_id", name="uq_order_item_stock"
        ),
        ForeignKeyConstraint(
            ["organization_id", "order_id"],
            ["orders.organization_id", "orders.id"],
            name="fk_order_item_org_order",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["catalog_products.organization_id", "catalog_products.id"],
            name="fk_order_item_org_product",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "branch_id"],
            ["organization_branches.organization_id", "organization_branches.id"],
            name="fk_order_item_org_branch",
            ondelete="RESTRICT",
        ),
        Index("ix_order_items_org_order", "organization_id", "order_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    order_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_sku_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
