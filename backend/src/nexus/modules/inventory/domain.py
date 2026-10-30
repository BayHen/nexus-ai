"""Inventory domain errors."""


class InventoryNotFoundError(Exception):
    """Raised when a tenant-scoped inventory resource is unavailable."""


class InventoryConflictError(Exception):
    """Raised for duplicate stock records or incompatible idempotent replay."""


class InsufficientStockError(Exception):
    """Raised when an operation violates the negative-stock policy."""


class InvalidTransferError(Exception):
    """Raised when a transfer source and destination are invalid."""
