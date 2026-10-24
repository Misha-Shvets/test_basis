# Payment System

Асинхронный сервис процессинга платежей на FastAPI, Dishka, SQLAlchemy,
PostgreSQL, RabbitMQ и FastStream.

## Структура

- `app/api` — HTTP-контракты и роутеры;
- `app/payment` — доменные dataclass-модели, порты и use cases;
- `app/infra/db` — SQLAlchemy, repositories и Alembic;
- `app/infra/messaging` — RabbitMQ topology;
- `app/worker.py` — FastStream handlers и lifecycle worker-а;
- `app/infra/messaging/worker_services.py` — outbox publisher, payment processor и webhook retry;
- `app/ioc.py` — регистрация зависимостей Dishka;
- `app/main.py` — composition root и регистрация приложения.

Доменные модели регистрируются в `app/infra/db/models.py` через
`mapper_registry.map_imperatively`. Функция `queryable_attr` сохраняет
типизированный доступ к SQLAlchemy `QueryableAttribute` в репозиториях.

Создание платежа атомарно сохраняет запись `payments` и событие в `outbox`.
Фоновый publisher отправляет событие в `payments.new`. Consumer эмулирует
платежный шлюз, обновляет статус и отправляет webhook. Ошибки обработки
повторяются до трёх раз с экспоненциальной задержкой, после чего сообщение
попадает в `payments.dlq`. Webhook также отправляется с тремя попытками.

## Запуск через Docker Compose

```bash
make build
make up
```

Compose запускает PostgreSQL, RabbitMQ, миграции, API и consumer.
API доступен по адресу `http://127.0.0.1:8000/docs`.

API-ключ по умолчанию: `test-api-key`.

## API

Создать платёж:

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: test-api-key' \
  -H 'Idempotency-Key: order-1001' \
  -d '{
    "amount": "1999.99",
    "currency": "RUB",
    "description": "Test payment",
    "metadata": {"order_id": "1001"},
    "webhook_url": "https://example.com/webhooks/payment"
  }'
```

Получить платёж:

```bash
curl http://localhost:8000/api/v1/payments/<payment_id> \
  -H 'X-API-Key: test-api-key'
```

## Локальная разработка

```bash
uv sync --extra dev
PYTHONPATH=app uv run alembic upgrade head
PYTHONPATH=app uv run uvicorn main:create_app --factory --reload
```

Consumer запускается отдельно:

```bash
uv run faststream run worker:app
```

Тесты используют реальный PostgreSQL через Dishka fixtures:

```bash
make build_test
make test
```

Применить миграции:

```bash
make migrate
```

Создать новую миграцию:

```bash
make migration message="add payment field"
```
