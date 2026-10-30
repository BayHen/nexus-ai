"""Catalog use cases with tenant and permission enforcement."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.catalog.domain import (
    CatalogNotFoundError,
    CategoryNotEmptyError,
    CategoryUnavailableError,
)
from nexus.modules.catalog.models import Category, Product
from nexus.modules.catalog.repository import CatalogRepository
from nexus.modules.organizations.domain import (
    Permission,
    TenantAccessDeniedError,
    TenantContext,
    has_permission,
)


class CatalogService:
    """Execute tenant-scoped catalog workflows in one transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = CatalogRepository(session)

    async def create_category(
        self, context: TenantContext, name: str, slug: str, description: str | None
    ) -> Category:
        self._authorize(context, Permission.CATALOG_WRITE)
        category = Category(
            organization_id=context.organization_id,
            name=name,
            slug=slug,
            description=description,
        )
        self._repository.add(category)
        await self._session.flush()
        return category

    async def get_category(self, context: TenantContext, category_id: UUID) -> Category:
        self._authorize(context, Permission.CATALOG_READ)
        category = await self._repository.category(context.organization_id, category_id)
        if category is None:
            raise CatalogNotFoundError
        return category

    async def list_categories(
        self,
        context: TenantContext,
        query: str | None,
        sort_by: str,
        sort_order: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Category], int]:
        self._authorize(context, Permission.CATALOG_READ)
        return await self._repository.list_categories(
            context.organization_id,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def update_category(
        self,
        context: TenantContext,
        category_id: UUID,
        *,
        name: str | None,
        slug: str | None,
        description: str | None,
        fields: set[str],
    ) -> Category:
        self._authorize(context, Permission.CATALOG_WRITE)
        category = await self._repository.category(context.organization_id, category_id, lock=True)
        if category is None:
            raise CatalogNotFoundError
        if "name" in fields:
            assert name is not None
            category.name = name
        if "slug" in fields:
            assert slug is not None
            category.slug = slug
        if "description" in fields:
            category.description = description
        return category

    async def delete_category(self, context: TenantContext, category_id: UUID) -> None:
        self._authorize(context, Permission.CATALOG_DELETE)
        category = await self._repository.category(context.organization_id, category_id, lock=True)
        if category is None:
            raise CatalogNotFoundError
        if await self._repository.category_has_products(context.organization_id, category_id):
            raise CategoryNotEmptyError
        category.deleted_at = datetime.now(UTC)

    async def create_product(
        self,
        context: TenantContext,
        *,
        name: str,
        description: str | None,
        price: Decimal,
        status: str,
        category_id: UUID | None,
    ) -> Product:
        self._authorize(context, Permission.CATALOG_WRITE)
        await self._validate_category(context.organization_id, category_id)
        sku = await self._repository.next_sku(context.organization_id)
        product = Product(
            organization_id=context.organization_id,
            category_id=category_id,
            sku=sku,
            name=name,
            description=description,
            price=price,
            status=status,
        )
        self._repository.add(product)
        await self._session.flush()
        return product

    async def get_product(self, context: TenantContext, product_id: UUID) -> Product:
        self._authorize(context, Permission.CATALOG_READ)
        product = await self._repository.product(context.organization_id, product_id)
        if product is None:
            raise CatalogNotFoundError
        return product

    async def list_products(
        self,
        context: TenantContext,
        *,
        query: str | None,
        category_id: UUID | None,
        status: str | None,
        min_price: Decimal | None,
        max_price: Decimal | None,
        sort_by: str,
        sort_order: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        self._authorize(context, Permission.CATALOG_READ)
        return await self._repository.list_products(
            context.organization_id,
            query=query,
            category_id=category_id,
            status=status,
            min_price=min_price,
            max_price=max_price,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    async def update_product(
        self,
        context: TenantContext,
        product_id: UUID,
        *,
        name: str | None,
        description: str | None,
        price: Decimal | None,
        status: str | None,
        category_id: UUID | None,
        fields: set[str],
    ) -> Product:
        self._authorize(context, Permission.CATALOG_WRITE)
        product = await self._repository.product(context.organization_id, product_id, lock=True)
        if product is None:
            raise CatalogNotFoundError
        if "category_id" in fields:
            await self._validate_category(context.organization_id, category_id)
            product.category_id = category_id
        if "name" in fields:
            assert name is not None
            product.name = name
        if "description" in fields:
            product.description = description
        if "price" in fields:
            assert price is not None
            product.price = price
        if "status" in fields:
            assert status is not None
            product.status = status
        return product

    async def delete_product(self, context: TenantContext, product_id: UUID) -> None:
        self._authorize(context, Permission.CATALOG_DELETE)
        product = await self._repository.product(context.organization_id, product_id, lock=True)
        if product is None:
            raise CatalogNotFoundError
        product.deleted_at = datetime.now(UTC)
        product.status = "archived"

    async def _validate_category(self, organization_id: UUID, category_id: UUID | None) -> None:
        if category_id is None:
            return
        category = await self._repository.category(organization_id, category_id, lock=True)
        if category is None:
            raise CategoryUnavailableError

    @staticmethod
    def _authorize(context: TenantContext, permission: Permission) -> None:
        if not has_permission(context.role, permission):
            raise TenantAccessDeniedError
