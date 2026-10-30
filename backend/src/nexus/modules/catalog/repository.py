"""Tenant-scoped catalog persistence adapter."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.catalog.models import Category, Product, SkuCounter


class CatalogRepository:
    """Require organization scope for every catalog query."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, instance: object) -> None:
        self._session.add(instance)

    async def next_sku(self, organization_id: UUID) -> str:
        statement = (
            insert(SkuCounter)
            .values(organization_id=organization_id, next_value=1)
            .on_conflict_do_update(
                index_elements=[SkuCounter.organization_id],
                set_={"next_value": SkuCounter.next_value + 1},
            )
            .returning(SkuCounter.next_value)
        )
        value = await self._session.scalar(statement)
        assert value is not None
        return f"PRD-{value:06d}"

    async def category(
        self, organization_id: UUID, category_id: UUID, *, lock: bool = False
    ) -> Category | None:
        statement = select(Category).where(
            Category.organization_id == organization_id,
            Category.id == category_id,
            Category.deleted_at.is_(None),
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def product(
        self, organization_id: UUID, product_id: UUID, *, lock: bool = False
    ) -> Product | None:
        statement = select(Product).where(
            Product.organization_id == organization_id,
            Product.id == product_id,
            Product.deleted_at.is_(None),
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def category_has_products(self, organization_id: UUID, category_id: UUID) -> bool:
        count = await self._session.scalar(
            select(func.count())
            .select_from(Product)
            .where(
                Product.organization_id == organization_id,
                Product.category_id == category_id,
                Product.deleted_at.is_(None),
            )
        )
        return bool(count)

    async def list_categories(
        self,
        organization_id: UUID,
        *,
        query: str | None,
        sort_by: str,
        sort_order: str,
        offset: int,
        limit: int,
    ) -> tuple[list[Category], int]:
        conditions = [Category.organization_id == organization_id, Category.deleted_at.is_(None)]
        if query:
            conditions.append(
                or_(Category.name.ilike(f"%{query}%"), Category.description.ilike(f"%{query}%"))
            )
        sort_column = {"name": Category.name, "created_at": Category.created_at}[sort_by]
        ordering = asc(sort_column) if sort_order == "asc" else desc(sort_column)
        rows = list(
            await self._session.scalars(
                select(Category)
                .where(*conditions)
                .order_by(ordering, Category.id)
                .offset(offset)
                .limit(limit)
            )
        )
        total = await self._session.scalar(
            select(func.count()).select_from(Category).where(*conditions)
        )
        return rows, int(total or 0)

    async def list_products(
        self,
        organization_id: UUID,
        *,
        query: str | None,
        category_id: UUID | None,
        status: str | None,
        min_price: Decimal | None,
        max_price: Decimal | None,
        sort_by: str,
        sort_order: str,
        offset: int,
        limit: int,
    ) -> tuple[list[Product], int]:
        conditions = [Product.organization_id == organization_id, Product.deleted_at.is_(None)]
        if query:
            conditions.append(
                or_(
                    Product.name.ilike(f"%{query}%"),
                    Product.description.ilike(f"%{query}%"),
                    Product.sku.ilike(f"%{query}%"),
                )
            )
        if category_id is not None:
            conditions.append(Product.category_id == category_id)
        if status:
            conditions.append(Product.status == status)
        if min_price is not None:
            conditions.append(Product.price >= min_price)
        if max_price is not None:
            conditions.append(Product.price <= max_price)
        sort_column = {
            "name": Product.name,
            "price": Product.price,
            "sku": Product.sku,
            "created_at": Product.created_at,
        }[sort_by]
        ordering = asc(sort_column) if sort_order == "asc" else desc(sort_column)
        rows = list(
            await self._session.scalars(
                select(Product)
                .where(*conditions)
                .order_by(ordering, Product.id)
                .offset(offset)
                .limit(limit)
            )
        )
        total = await self._session.scalar(
            select(func.count()).select_from(Product).where(*conditions)
        )
        return rows, int(total or 0)
