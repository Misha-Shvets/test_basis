"""Services used by the FastStream worker."""

import asyncio
import random
from typing import Any
from uuid import UUID

import httpx
from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infra.db.repositories import SqlAlchemyOutboxRepository
from infra.messaging.broker import (
    DLQ_QUEUE,
    DLX_EXCHANGE,
    PAYMENTS_EXCHANGE,
    PAYMENTS_QUEUE,
)
from payment.dtos import PaymentStatus
from payment.services import PaymentService

MAX_PROCESSING_ATTEMPTS = 3


class WebhookSender:
    """Send payment webhooks with bounded exponential retry."""

    async def send(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        webhook_url: str,
        idempotency_key: str,
    ) -> None:
        """Send a webhook with three exponential-backoff attempts."""
        last_error: Exception | None = None
        for attempt in range(MAX_PROCESSING_ATTEMPTS):
            try:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Idempotency-Key": idempotency_key},
                )
                response.raise_for_status()
                return
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
                if attempt < MAX_PROCESSING_ATTEMPTS - 1:
                    await asyncio.sleep(2**attempt)
        raise RuntimeError("Webhook delivery failed") from last_error


class PaymentProcessor:
    """Process payment messages and route failures to retry or DLQ."""

    def __init__(
        self,
        service: PaymentService,
        broker: RabbitBroker,
        webhook_sender: WebhookSender,
        client: httpx.AsyncClient,
    ) -> None:
        self._service = service
        self._broker = broker
        self._webhook_sender = webhook_sender
        self._client = client

    async def process(self, payload: dict[str, Any]) -> None:
        """Process one payment message."""
        attempt = int(payload.get("_attempt", 1))
        try:
            payment_id = UUID(str(payload["payment_id"]))
            payment = await self._service.get(payment_id)
            if payment is None or payment.webhook_sent_at is not None:
                return
            if payment.status is PaymentStatus.PENDING:
                await asyncio.sleep(random.uniform(2, 5))
                result = (
                    PaymentStatus.SUCCEEDED
                    if random.random() < 0.9
                    else PaymentStatus.FAILED
                )
                await self._service.mark_processed(payment_id, result)
            else:
                result = payment.status
        except Exception as error:
            await self._retry_processing(payload, error, attempt)
            return

        webhook_payload = {
            "payment_id": str(payment_id),
            "status": result.value,
        }
        try:
            await self._webhook_sender.send(
                client=self._client,
                payload=webhook_payload,
                webhook_url=str(payload["webhook_url"]),
                idempotency_key=str(payment_id),
            )
        except RuntimeError as error:
            await self._publish_dead_letter(
                {
                    **webhook_payload,
                    "webhook_url": payload["webhook_url"],
                },
                error,
                MAX_PROCESSING_ATTEMPTS,
            )
        else:
            await self._service.mark_webhook_sent(payment_id)

    async def _publish_dead_letter(
        self,
        payload: dict[str, Any],
        error: Exception,
        attempt: int,
    ) -> None:
        """Publish a failed message to the dead-letter queue."""
        await self._broker.publish(
            {
                **payload,
                "error": str(error),
                "attempt": attempt,
            },
            exchange=DLX_EXCHANGE,
            routing_key=DLQ_QUEUE.name,
        )

    async def _retry_processing(
        self,
        payload: dict[str, Any],
        error: Exception,
        attempt: int,
    ) -> None:
        """Retry payment processing or move the message to the DLQ."""
        if attempt >= MAX_PROCESSING_ATTEMPTS:
            await self._publish_dead_letter(payload, error, attempt)
            return

        await asyncio.sleep(2 ** (attempt - 1))
        await self._broker.publish(
            {
                **payload,
                "_attempt": attempt + 1,
            },
            exchange=PAYMENTS_EXCHANGE,
            routing_key=PAYMENTS_QUEUE.name,
        )


class OutboxPublisher:
    """Publish pending outbox events with database-backed retry state."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        broker: RabbitBroker,
    ) -> None:
        self._session_factory = session_factory
        self._broker = broker

    async def run(self) -> None:
        """Poll and publish outbox events until cancelled."""
        while True:
            async with self._session_factory() as session:
                repository = SqlAlchemyOutboxRepository(session)
                event = await repository.claim_next()
                if event is None:
                    await asyncio.sleep(1)
                    continue
                try:
                    await self._broker.publish(
                        event.payload,
                        exchange=PAYMENTS_EXCHANGE,
                        routing_key=PAYMENTS_QUEUE.name,
                    )
                except Exception as error:
                    await repository.mark_failed(event, str(error))
                else:
                    await repository.mark_published(event)
                await session.commit()
