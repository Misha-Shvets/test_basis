"""SQLAlchemy implementations of payment ports."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import exc as sa_exc
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models import payments_table, queryable_attr
from infra.db.errors import DuplicateIdempotencyKeyError
from payment.dtos import OutboxEvent, Payment, PaymentStatus


class SqlAlchemyPaymentRepository:
    """Payment repository backed by SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_with_event(
        self,
        payment: Payment,
        event: OutboxEvent,
    ) -> Payment:
        """Persist payment and outbox event in one transaction."""
        self._session.add(payment)
        self._session.add(event)
        try:
            await self._session.flush()
        except sa_exc.IntegrityError as error:
            await self._session.rollback()
            raise DuplicateIdempotencyKeyError(
                "Payment idempotency key already exists",
            ) from error
        return payment

    async def get(self, payment_id: UUID) -> Payment | None:
        statement = select(Payment).where(
            queryable_attr(Payment.id) == payment_id,
        )
        return await self._session.scalar(statement)

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        """Find a payment by its idempotency key."""
        statement = select(Payment).where(
            queryable_attr(Payment.idempotency_key) == key,
        )
        return await self._session.scalar(statement)

    async def update_status(
        self,
        payment_id: UUID,
        status: PaymentStatus,
        processed_at: datetime,
    ) -> Payment | None:
        """Update a payment status."""
        statement = (
            update(payments_table)
            .where(payments_table.c.id == payment_id)
            .values(status=status, processed_at=processed_at)
            .returning(*payments_table.c)
        )
        result = await self._session.execute(statement)
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return Payment(**row)

    async def mark_webhook_sent(
        self,
        payment_id: UUID,
        sent_at: datetime,
    ) -> Payment | None:
        """Persist successful webhook delivery."""
        statement = (
            update(payments_table)
            .where(payments_table.c.id == payment_id)
            .values(webhook_sent_at=sent_at)
            .returning(*payments_table.c)
        )
        result = await self._session.execute(statement)
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return Payment(**row)


class SqlAlchemyOutboxRepository:
    """Repository for claiming and publishing outbox events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_next(self) -> OutboxEvent | None:
        """Claim one due unpublished event."""
        statement = (
            select(OutboxEvent)
            .where(
                queryable_attr(OutboxEvent.published_at).is_(None),
                queryable_attr(OutboxEvent.next_attempt_at) <= datetime.now(UTC),
            )
            .order_by(queryable_attr(OutboxEvent.next_attempt_at))
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        return await self._session.scalar(statement)

    async def mark_published(self, event: OutboxEvent) -> None:
        """Mark an event as successfully published."""
        event.published_at = datetime.now(UTC)
        await self._session.flush()

    async def mark_failed(self, event: OutboxEvent, error: str) -> None:
        """Record a failed publish attempt with a backoff delay."""
        event.attempts += 1
        event.last_error = error[:2000]
        event.next_attempt_at = datetime.now(UTC) + timedelta(
            seconds=2 ** min(event.attempts, 6),
        )
        await self._session.flush()
