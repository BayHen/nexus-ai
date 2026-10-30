"""Catalog domain errors."""


class CatalogNotFoundError(Exception):
    """Raised when a tenant-scoped catalog resource is not visible."""


class CatalogConflictError(Exception):
    """Raised when a catalog uniqueness invariant conflicts."""


class CategoryNotEmptyError(Exception):
    """Raised when a category still owns non-deleted products."""


class CategoryUnavailableError(Exception):
    """Raised when a product references a missing or deleted category."""
