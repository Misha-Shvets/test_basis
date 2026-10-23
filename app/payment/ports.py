"""Ports used by payment use cases."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from payment.dtos import OutboxEvent, Payment, PaymentStatus


class PaymentRepository(Protocol):
    """Persistence contract for payments."""

    async def create_with_event(
        self,
        payment: Payment,
        event: OutboxEvent,
    ) -> Payment:
        """Persist a payment and its outbox event atomically."""

    async def get(self, payment_id: UUID) -> Payment | None:
        """Find a payment by identifier."""

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        """Find a payment by idempotency key."""

    async def update_status(
        self,
        payment_id: UUID,
        status: PaymentStatus,
        processed_at: datetime,
    ) -> Payment | None:
        """Update payment processing status."""

    async def mark_webhook_sent(
        self,
        payment_id: UUID,
        sent_at: datetime,
    ) -> Payment | None:
        """Persist successful webhook delivery."""
