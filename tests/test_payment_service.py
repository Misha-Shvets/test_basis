"""Payment service and API tests."""

from decimal import Decimal

import pytest
from dishka import AsyncContainer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models import outbox_table
from payment.dtos import PaymentStatus
from payment.errors import IdempotencyConflictError
from payment.ports import PaymentRepository
from payment.services import PaymentService


@pytest.mark.asyncio
async def test_create_payment_writes_outbox_event(
    request_container: AsyncContainer,
    clean_database: None,
) -> None:
    payment_service = await request_container.get(PaymentService)
    repository = await request_container.get(PaymentRepository)
    payment = await payment_service.create(
        amount=Decimal("10.50"),
        currency="RUB",
        metadata={"order_id": "1"},
        idempotency_key="order-1",
        webhook_url="https://example.com/hook",
    )
    session = await request_container.get(AsyncSession)
    await session.commit()

    assert payment.status is PaymentStatus.PENDING
    stored = await repository.get(payment.id)
    event_count = await session.scalar(
        select(func.count()).select_from(outbox_table),
    )
    assert stored is not None
    assert event_count == 1


@pytest.mark.asyncio
async def test_same_idempotency_key_returns_existing_payment(
    request_container: AsyncContainer,
    clean_database: None,
) -> None:
    payment_service = await request_container.get(PaymentService)
    first = await payment_service.create(
        amount=Decimal("10.50"),
        currency="EUR",
        idempotency_key="same-key",
        webhook_url="https://example.com/hook",
    )

    second = await payment_service.create(
        amount=Decimal("10.50"),
        currency="EUR",
        metadata={},
        idempotency_key="same-key",
        webhook_url="https://example.com/hook",
    )
    session = await request_container.get(AsyncSession)
    await session.commit()
    event_count = await session.scalar(
        select(func.count()).select_from(outbox_table),
    )

    assert second.id == first.id
    assert second.amount == Decimal("10.50")
    assert event_count == 1


@pytest.mark.asyncio
async def test_same_idempotency_key_with_different_data_conflicts(
    request_container: AsyncContainer,
    clean_database: None,
) -> None:
    payment_service = await request_container.get(PaymentService)
    await payment_service.create(
        amount=Decimal("10.50"),
        currency="RUB",
        idempotency_key="conflicting-key",
        webhook_url="https://example.com/hook",
    )

    with pytest.raises(IdempotencyConflictError):
        await payment_service.create(
            amount=Decimal("99.99"),
            currency="RUB",
            idempotency_key="conflicting-key",
            webhook_url="https://example.com/hook",
        )
