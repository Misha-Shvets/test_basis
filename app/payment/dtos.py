"""Payment domain models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class Currency(StrEnum):
    """Supported payment currencies."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatus(StrEnum):
    """Lifecycle state of a payment."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class Payment:
    """Payment aggregate persisted by the infrastructure layer."""

    amount: Decimal
    currency: Currency
    id: UUID = field(default_factory=uuid4)
    status: PaymentStatus = PaymentStatus.PENDING
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    webhook_url: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    processed_at: datetime | None = None
    webhook_sent_at: datetime | None = None


@dataclass
class OutboxEvent:
    """Event waiting to be published to the message broker."""

    event_type: str
    aggregate_id: UUID
    payload: dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    attempts: int = 0
    published_at: datetime | None = None
    next_attempt_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    last_error: str | None = None
