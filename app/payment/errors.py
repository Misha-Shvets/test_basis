"""Business errors for payment use cases."""


class PaymentError(Exception):
    """Base class for payment business errors."""


class InvalidPaymentAmountError(PaymentError):
    """Raised when a payment amount is not positive."""


class IdempotencyKeyRequiredError(PaymentError):
    """Raised when an idempotency key is empty."""


class UnsupportedCurrencyError(PaymentError):
    """Raised when a payment currency is not supported."""


class IdempotencyConflictError(PaymentError):
    """Raised when an idempotency key is reused with different data."""


class PaymentNotFoundError(PaymentError):
    """Raised when a requested payment does not exist."""
