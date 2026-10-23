"""SQLAlchemy registration for payment dataclass models."""

from typing import TypeVar, cast

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import QueryableAttribute, registry

from payment.dtos import Currency, OutboxEvent, Payment, PaymentStatus

_T = TypeVar("_T")


def queryable_attr(value: _T) -> QueryableAttribute[_T]:
    """Expose a mapped field as a type-safe SQLAlchemy query attribute.

    :param T value: The value to cast.
    :return QueryableAttribute[T]: The casted value.
    """
    return cast("QueryableAttribute[_T]", value)


mapper_registry = registry()
metadata: MetaData = mapper_registry.metadata

payments_table = Table(
    "payments",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("amount", Numeric(18, 2), nullable=False),
    Column(
        "currency",
        Enum(
            Currency,
            name="currency",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    ),
    Column(
        "status",
        Enum(
            PaymentStatus,
            name="payment_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    ),
    Column("description", String(500), nullable=True),
    Column("metadata", JSON, nullable=False, default=dict),
    Column("idempotency_key", String(255), nullable=False, unique=True),
    Column("webhook_url", String(2048), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("processed_at", DateTime(timezone=True), nullable=True),
    Column("webhook_sent_at", DateTime(timezone=True), nullable=True),
)

mapper_registry.map_imperatively(Payment, payments_table)

outbox_table = Table(
    "outbox",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("event_type", String(255), nullable=False),
    Column("aggregate_id", PG_UUID(as_uuid=True), nullable=False, index=True),
    Column("payload", JSON, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("published_at", DateTime(timezone=True), nullable=True),
    Column("next_attempt_at", DateTime(timezone=True), nullable=False),
    Column("last_error", String(2000), nullable=True),
)

mapper_registry.map_imperatively(OutboxEvent, outbox_table)
