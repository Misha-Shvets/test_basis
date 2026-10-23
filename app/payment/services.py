"""Payment use cases."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from infra.db.errors import DuplicateIdempotencyKeyError
from payment.dtos import Currency, OutboxEvent, Payment, PaymentStatus
from payment.errors import (
    IdempotencyConflictError,
    IdempotencyKeyRequiredError,
    InvalidPaymentAmountError,
    PaymentNotFoundError,
    UnsupportedCurrencyError,
)
from payment.ports import PaymentRepository


class PaymentService:
    """Application service containing payment business rules."""

    def __init__(self, repository: PaymentRepository) -> None:
        self._repository = repository

    async def create(
        self,
        amount: Decimal,
        currency: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str = "",
        webhook_url: str = "",
    ) -> Payment:
        """Create a payment after validating its business invariants."""
        if amount <= 0:
            raise InvalidPaymentAmountError(
                "Payment amount must be greater than zero",
            )
        normalized_idempotency_key = idempotency_key.strip()
        if not normalized_idempotency_key:
            raise IdempotencyKeyRequiredError("Idempotency key is required")
        try:
            payment_currency = Currency(currency.upper())
        except ValueError as error:
            raise UnsupportedCurrencyError(
                "Currency must be RUB, USD or EUR",
            ) from error

        existing = await self._repository.get_by_idempotency_key(
            normalized_idempotency_key,
        )
        if existing is not None:
            if not self._matches_existing(
                existing,
                amount,
                payment_currency,
                description,
                metadata,
                webhook_url,
            ):
                raise IdempotencyConflictError(
                    "Idempotency key is already used with different payment data",
                )
            return existing

        payment = Payment(
            amount=amount,
            currency=payment_currency,
            description=description,
            metadata=metadata or {},
            idempotency_key=normalized_idempotency_key,
            webhook_url=webhook_url,
        )
        event = OutboxEvent(
            event_type="payments.new",
            aggregate_id=payment.id,
            payload={
                "payment_id": str(payment.id),
                "amount": str(payment.amount),
                "currency": payment.currency.value,
                "description": payment.description,
                "metadata": payment.metadata,
                "webhook_url": payment.webhook_url,
            },
        )
        try:
            return await self._repository.create_with_event(payment, event)
        except DuplicateIdempotencyKeyError:
            existing = await self._repository.get_by_idempotency_key(
                normalized_idempotency_key,
            )
            if existing is not None:
                if not self._matches_existing(
                    existing,
                    amount,
                    payment_currency,
                    description,
                    metadata,
                    webhook_url,
                ):
                    raise IdempotencyConflictError(
                        "Idempotency key is already used with different payment data",
                    )
                return existing
            raise

    @staticmethod
    def _matches_existing(
        existing: Payment,
        amount: Decimal,
        currency: Currency,
        description: str | None,
        metadata: dict[str, Any] | None,
        webhook_url: str,
    ) -> bool:
        """Check whether a retry contains the original payment data."""
        return (
            existing.amount == amount
            and existing.currency is currency
            and existing.description == description
            and existing.metadata == (metadata or {})
            and existing.webhook_url == webhook_url
        )

    async def get(self, payment_id: UUID) -> Payment | None:
        """Return a payment by identifier."""
        return await self._repository.get(payment_id)

    async def get_or_raise(self, payment_id: UUID) -> Payment:
        """Return a payment or raise a business-level not-found error."""
        payment = await self.get(payment_id)
        if payment is None:
            raise PaymentNotFoundError("Payment not found")
        return payment

    async def mark_processed(
        self,
        payment_id: UUID,
        status: PaymentStatus,
    ) -> Payment | None:
        """Set the final status of a payment."""
        return await self._repository.update_status(
            payment_id,
            status,
            datetime.now(UTC),
        )

    async def mark_webhook_sent(self, payment_id: UUID) -> Payment | None:
        """Persist successful webhook delivery."""
        return await self._repository.mark_webhook_sent(
            payment_id,
            datetime.now(UTC),
        )
