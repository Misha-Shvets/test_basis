"""FastStream RabbitMQ topology."""

from faststream.rabbit import RabbitExchange, RabbitQueue

PAYMENTS_EXCHANGE = RabbitExchange("payments", durable=True)
DLX_EXCHANGE = RabbitExchange("payments.dlx", durable=True)
DLQ_QUEUE = RabbitQueue("payments.dlq", durable=True)
PAYMENTS_QUEUE = RabbitQueue(
    "payments.new",
    durable=True,
    arguments={
        "x-dead-letter-exchange": DLX_EXCHANGE.name,
        "x-dead-letter-routing-key": DLQ_QUEUE.name,
    },
)
