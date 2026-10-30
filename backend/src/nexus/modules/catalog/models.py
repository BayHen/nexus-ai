"""SQLAlchemy mappings for tenant-scoped products and categories."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from nexus.platform.database.base import Base


class Category(Base):
    """Soft-deletable tenant-owned product category."""

    __tablename__ = "catalog_categories"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_catalog_categories_org_id"),
        Index(
            "uq_catalog_categories_org_name_active",
            "organization_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_catalog_categories_org_slug_active",
            "organization_id",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Product(Base):
    """Soft-deletable tenant-owned product with an immutable generated SKU."""

    __tablename__ = "catalog_products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="non_negative_price"),
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="valid_status"),
        UniqueConstraint("organization_id", "sku", name="uq_catalog_products_org_sku"),
        ForeignKeyConstraint(
            ["organization_id", "category_id"],
            ["catalog_categories.organization_id", "catalog_categories.id"],
            name="fk_catalog_products_org_category",
            ondelete="RESTRICT",
        ),
        Index("ix_catalog_products_org_name", "organization_id", "name"),
        Index("ix_catalog_products_org_status", "organization_id", "status"),
        Index("ix_catalog_products_org_category", "organization_id", "category_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    sku: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SkuCounter(Base):
    """Atomic per-tenant source for generated product SKUs."""

    __tablename__ = "catalog_sku_counters"
    __table_args__ = (CheckConstraint("next_value > 0", name="positive_value"),)

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    next_value: Mapped[int] = mapped_column(Integer, nullable=False)
