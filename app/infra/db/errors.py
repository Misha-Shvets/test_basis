"""Persistence errors for the database adapters."""


class RepositoryError(Exception):
    """Base class for database repository errors."""


class DuplicateIdempotencyKeyError(RepositoryError):
    """Raised when a payment idempotency key already exists."""
