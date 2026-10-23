"""Pydantic models for the payment API."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field

from payment.dtos import Payment


class CreatePaymentRequest(BaseModel):
    """Request to create a payment."""

    amount: Decimal = Field(gt=0)
    currency: str
    description: str | None = Field(default=None, max_length=500)
    metadata: dict[str, object] = Field(default_factory=dict)
    webhook_url: AnyHttpUrl


class PaymentResponse(BaseModel):
    """Public payment representation."""

    id: UUID
    amount: Decimal
    currency: str
    status: str
    description: str | None
    metadata: dict[str, object]
    webhook_url: str
    idempotency_key: str
    created_at: datetime
    processed_at: datetime | None

    @classmethod
    def from_domain(cls, payment: Payment) -> "PaymentResponse":
        """Convert a domain object into an API response."""
        return cls(
            id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            status=payment.status,
            description=payment.description,
            metadata=payment.metadata,
            webhook_url=payment.webhook_url,
            idempotency_key=payment.idempotency_key,
            created_at=payment.created_at,
            processed_at=payment.processed_at,
        )
