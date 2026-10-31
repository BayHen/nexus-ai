"""Tenant-scoped Product and Category REST APIs."""

from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.auth.dependencies import get_transaction
from nexus.modules.catalog.domain import (
    CatalogNotFoundError,
    CategoryNotEmptyError,
    CategoryUnavailableError,
)
from nexus.modules.catalog.models import Category, Product
from nexus.modules.catalog.schemas import (
    CategoryCreateRequest,
    CategoryPageResponse,
    CategoryResponse,
    CategoryUpdateRequest,
    ProductCreateRequest,
    ProductPageResponse,
    ProductResponse,
    ProductUpdateRequest,
)
from nexus.modules.catalog.service import CatalogService
from nexus.modules.organizations.dependencies import TenantContextDependency
from nexus.modules.organizations.domain import (
    Permission,
    TenantAccessDeniedError,
    has_permission,
)
from nexus.platform.api.errors import ApplicationError
from nexus.platform.cache.service import CacheService, schedule_invalidation, tenant_cache_key

router = APIRouter(tags=["catalog"])
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]
PageDependency = Annotated[int, Query(ge=1)]
PageSizeDependency = Annotated[int, Query(ge=1, le=100)]


def get_cache(request: Request) -> CacheService:
    return cast(CacheService, request.app.state.cache_service)


CacheDependency = Annotated[CacheService, Depends(get_cache)]


def category_response(category: Category) -> CategoryResponse:
    return CategoryResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def product_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        category_id=product.category_id,
        sku=product.sku,
        name=product.name,
        description=product.description,
        price=product.price,
        status=cast(Literal["draft", "active", "archived"], product.status),
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def not_found() -> ApplicationError:
    return ApplicationError(
        code="resource_not_found",
        message="The requested resource was not found.",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def access_denied() -> ApplicationError:
    return ApplicationError(
        code="tenant_access_denied",
        message="You do not have permission to perform this action.",
        status_code=status.HTTP_403_FORBIDDEN,
    )


def conflict(
    message: str = "The catalog resource conflicts with existing data.",
) -> ApplicationError:
    return ApplicationError(
        code="catalog_conflict", message=message, status_code=status.HTTP_409_CONFLICT
    )


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CategoryCreateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> CategoryResponse:
    try:
        category = await CatalogService(session).create_category(
            context, body.name, body.slug, body.description
        )
    except TenantAccessDeniedError as exc:
        raise access_denied() from exc
    except IntegrityError as exc:
        raise conflict() from exc
    return category_response(category)


@router.get("/categories", response_model=CategoryPageResponse)
async def list_categories(
    session: SessionDependency,
    context: TenantContextDependency,
    page: PageDependency = 1,
    page_size: PageSizeDependency = 20,
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    sort_by: Literal["name", "created_at"] = "name",
    sort_order: Literal["asc", "desc"] = "asc",
) -> CategoryPageResponse:
    try:
        items, total = await CatalogService(session).list_categories(
            context, query, sort_by, sort_order, page, page_size
        )
    except TenantAccessDeniedError as exc:
        raise access_denied() from exc
    return CategoryPageResponse(
        items=[category_response(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: UUID,
    session: SessionDependency,
    context: TenantContextDependency,
    cache: CacheDependency,
    request: Request,
) -> CategoryResponse:
    if not has_permission(context.role, Permission.CATALOG_READ):
        raise access_denied()
    key = tenant_cache_key(context.organization_id, "category", category_id)
    cached = await cache.get_json(key)
    if cached is not None:
        return CategoryResponse.model_validate(cached)
    try:
        response = category_response(
            await CatalogService(session).get_category(context, category_id)
        )
    except CatalogNotFoundError as exc:
        raise not_found() from exc
    await cache.set_json(
        key,
        response.model_dump(mode="json"),
        request.app.state.settings.cache_ttl_seconds,
    )
    return response


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    body: CategoryUpdateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> CategoryResponse:
    try:
        category = await CatalogService(session).update_category(
            context,
            category_id,
            name=body.name,
            slug=body.slug,
            description=body.description,
            fields=body.model_fields_set,
        )
    except CatalogNotFoundError as exc:
        raise not_found() from exc
    except TenantAccessDeniedError as exc:
        raise access_denied() from exc
    except IntegrityError as exc:
        raise conflict() from exc
    schedule_invalidation(
        session, tenant_cache_key(context.organization_id, "category", category_id)
    )
    return category_response(category)


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: UUID, session: SessionDependency, context: TenantContextDependency
) -> Response:
    try:
        await CatalogService(session).delete_category(context, category_id)
    except CatalogNotFoundError as exc:
        raise not_found() from exc
    except TenantAccessDeniedError as exc:
        raise access_denied() from exc
    except CategoryNotEmptyError as exc:
        raise conflict("The category cannot be deleted while it contains products.") from exc
    schedule_invalidation(
        session, tenant_cache_key(context.organization_id, "category", category_id)
    )
    return Response(status_code=204)


@router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> ProductResponse:
    try:
        product = await CatalogService(session).create_product(
            context,
            name=body.name,
            description=body.description,
            price=body.price,
            status=body.status,
            category_id=body.category_id,
        )
    except TenantAccessDeniedError as exc:
        raise access_denied() from exc
    except CategoryUnavailableError as exc:
        raise ApplicationError(
            code="category_unavailable",
            message="The selected category is unavailable.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc
    return product_response(product)


@router.get("/products", response_model=ProductPageResponse)
async def list_products(
    session: SessionDependency,
    context: TenantContextDependency,
    page: PageDependency = 1,
    page_size: PageSizeDependency = 20,
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    category_id: UUID | None = None,
    product_status: Annotated[
        Literal["draft", "active", "archived"] | None, Query(alias="status")
    ] = None,
    min_price: Annotated[Decimal | None, Query(ge=0)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    sort_by: Literal["name", "price", "sku", "created_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> ProductPageResponse:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ApplicationError(
            code="invalid_price_range",
            message="The minimum price cannot exceed the maximum price.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    try:
        items, total = await CatalogService(session).list_products(
            context,
            query=query,
            category_id=category_id,
            status=product_status,
            min_price=min_price,
            max_price=max_price,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    except TenantAccessDeniedError as exc:
        raise access_denied() from exc
    return ProductPageResponse(
        items=[product_response(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    session: SessionDependency,
    context: TenantContextDependency,
    cache: CacheDependency,
    request: Request,
) -> ProductResponse:
    if not has_permission(context.role, Permission.CATALOG_READ):
        raise access_denied()
    key = tenant_cache_key(context.organization_id, "product", product_id)
    cached = await cache.get_json(key)
    if cached is not None:
        return ProductResponse.model_validate(cached)
    try:
        response = product_response(
            await CatalogService(session).get_product(context, product_id)
        )
    except CatalogNotFoundError as exc:
        raise not_found() from exc
    await cache.set_json(
        key,
        response.model_dump(mode="json"),
        request.app.state.settings.cache_ttl_seconds,
    )
    return response


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    body: ProductUpdateRequest,
    session: SessionDependency,
    context: TenantContextDependency,
) -> ProductResponse:
    try:
        product = await CatalogService(session).update_product(
            context,
            product_id,
            name=body.name,
            description=body.description,
            price=body.price,
            status=body.status,
            category_id=body.category_id,
            fields=body.model_fields_set,
        )
    except CatalogNotFoundError as exc:
        raise not_found() from exc
    except TenantAccessDeniedError as exc:
        raise access_denied() from exc
    except CategoryUnavailableError as exc:
        raise ApplicationError(
            code="category_unavailable",
            message="The selected category is unavailable.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc
    schedule_invalidation(
        session, tenant_cache_key(context.organization_id, "product", product_id)
    )
    return product_response(product)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID, session: SessionDependency, context: TenantContextDependency
) -> Response:
    try:
        await CatalogService(session).delete_product(context, product_id)
    except CatalogNotFoundError as exc:
        raise not_found() from exc
    except TenantAccessDeniedError as exc:
        raise access_denied() from exc
    schedule_invalidation(
        session, tenant_cache_key(context.organization_id, "product", product_id)
    )
    return Response(status_code=204)
