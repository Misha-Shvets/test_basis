"""Unit tests for worker retry and dead-letter behavior."""

import asyncio
from typing import cast
from unittest.mock import AsyncMock

import httpx
import pytest
from faststream.rabbit import RabbitBroker

from infra.messaging.broker import DLX_EXCHANGE, PAYMENTS_EXCHANGE, PAYMENTS_QUEUE
from infra.messaging.worker_services import PaymentProcessor, WebhookSender
from payment.services import PaymentService


class SuccessfulResponse:
    """Minimal successful HTTP response test double."""

    def raise_for_status(self) -> None:
        """Mark the response as successful."""


def make_processor(broker: AsyncMock) -> PaymentProcessor:
    """Create a processor for retry-only tests."""
    return PaymentProcessor(
        cast(PaymentService, object()),
        cast(RabbitBroker, broker),
        cast(WebhookSender, object()),
        cast(httpx.AsyncClient, object()),
    )


@pytest.mark.asyncio
async def test_processing_error_is_republished_with_incremented_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = AsyncMock()
    processor = make_processor(broker)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    await processor._retry_processing(
        {"payment_id": "payment-1"},
        RuntimeError("temporary failure"),
        attempt=1,
    )

    broker.publish.assert_awaited_once()
    message = broker.publish.await_args.args[0]
    assert message["_attempt"] == 2
    assert broker.publish.await_args.kwargs["exchange"] is PAYMENTS_EXCHANGE
    assert (
        broker.publish.await_args.kwargs["routing_key"]
        == PAYMENTS_QUEUE.name
    )


@pytest.mark.asyncio
async def test_third_processing_error_is_sent_to_dlq() -> None:
    broker = AsyncMock()
    processor = make_processor(broker)

    await processor._retry_processing(
        {"payment_id": "payment-1"},
        RuntimeError("permanent failure"),
        attempt=3,
    )

    broker.publish.assert_awaited_once()
    message = broker.publish.await_args.args[0]
    assert message["attempt"] == 3
    assert message["error"] == "permanent failure"
    assert broker.publish.await_args.kwargs["exchange"] is DLX_EXCHANGE


@pytest.mark.asyncio
async def test_webhook_sender_retries_three_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncMock()
    client.post.side_effect = [
        httpx.HTTPError("temporary failure"),
        httpx.HTTPError("temporary failure"),
        SuccessfulResponse(),
    ]
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    await WebhookSender().send(
        client,
        {"payment_id": "payment-1", "status": "succeeded"},
        "https://example.com/webhook",
        "payment-1",
    )

    assert client.post.await_count == 3
