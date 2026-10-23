"""Infrastructure-specific dependency providers."""

from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, from_context, provide
from faststream.rabbit import RabbitBroker
from infra.messaging.worker_services import (
    OutboxPublisher,
    PaymentProcessor,
    WebhookSender,
)



class WorkerProvider(Provider):
    """Provider reserved for worker-only adapters."""

    broker = from_context(provides=RabbitBroker, scope=Scope.APP)

    @provide(scope=Scope.REQUEST)
    async def webhook_client(self) -> AsyncIterator[httpx.AsyncClient]:
        """Provide a short-lived client for webhook delivery."""
        async with httpx.AsyncClient(timeout=10) as client:
            yield client

    webhook_sender = provide(WebhookSender, scope=Scope.REQUEST)
    payment_processor = provide(PaymentProcessor, scope=Scope.REQUEST)
    outbox_publisher = provide(OutboxPublisher, scope=Scope.APP)
