"""Payment outbox publisher and RabbitMQ consumer."""

import asyncio
from contextlib import suppress
from typing import Any

from dishka import AsyncContainer, Scope, make_async_container
from faststream import FastStream
from faststream.rabbit import RabbitBroker

from config import Settings
from infra.ioc import WorkerProvider
from infra.messaging.broker import (
    DLQ_QUEUE,
    DLX_EXCHANGE,
    PAYMENTS_EXCHANGE,
    PAYMENTS_QUEUE,
)
from infra.messaging.worker_services import OutboxPublisher, PaymentProcessor
from ioc import MainProvider

settings = Settings.from_env()
broker = RabbitBroker(settings.rabbit_url)
app = FastStream(broker)


async def _run_outbox(container: AsyncContainer) -> None:
    """Resolve and run the outbox publisher in the application scope."""
    async with container(scope=Scope.APP) as app_container:
        publisher = await app_container.get(OutboxPublisher)
        await publisher.run()


@broker.subscriber(
    queue=PAYMENTS_QUEUE,
    exchange=PAYMENTS_EXCHANGE,
)
async def process_payment(payload: dict[str, Any]) -> None:
    """Process one payment message through the application service."""
    container = app.context.get("container")
    if container is None:
        raise RuntimeError("Worker container is not initialized")
    async with container(scope=Scope.REQUEST) as request_container:
        processor = await request_container.get(PaymentProcessor)
        await processor.process(payload)


@app.after_startup
async def startup() -> None:
    """Declare messaging resources and start background work."""
    dlq_exchange = await broker.declare_exchange(DLX_EXCHANGE)
    dlq = await broker.declare_queue(DLQ_QUEUE)
    await dlq.bind(dlq_exchange, routing_key=DLQ_QUEUE.name)
    container = make_async_container(
        MainProvider(),
        WorkerProvider(),
        context={Settings: settings, RabbitBroker: broker},
    )
    app.context.set_global("container", container)
    app.context.set_global(
        "publisher_task",
        asyncio.create_task(_run_outbox(container)),
    )


@app.on_shutdown
async def shutdown() -> None:
    """Stop background work and release the DI container."""
    publisher_task = app.context.get("publisher_task")
    if publisher_task is not None:
        publisher_task.cancel()
        with suppress(asyncio.CancelledError):
            await publisher_task
    container = app.context.get("container")
    if container is not None:
        await container.close()
