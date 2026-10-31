"""Framework-independent order errors and state rules."""


class OrderNotFoundError(LookupError):
    """Raised when an order or item is unavailable in the active tenant."""


class OrderConflictError(RuntimeError):
    """Raised for invalid state transitions or conflicting order data."""


class OrderInsufficientStockError(RuntimeError):
    """Raised when confirmation cannot deduct all requested stock."""
