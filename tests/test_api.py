"""HTTP API tests using the Dishka-backed application fixture."""

from uuid import UUID

import httpx
import pytest


@pytest.mark.asyncio
async def test_create_and_get_payment(
    client: httpx.AsyncClient,
    clean_database: None,
) -> None:
    """Create a payment and read it back through the API."""
    headers = {
        "X-API-Key": "test-api-key",
        "Idempotency-Key": "api-order-1",
    }
    response = await client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "amount": "25.50",
            "currency": "RUB",
            "metadata": {"order_id": "1"},
            "webhook_url": "https://example.com/webhook",
        },
    )

    assert response.status_code == 202
    payment_id = UUID(response.json()["id"])

    conflict_response = await client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "amount": "99.99",
            "currency": "RUB",
            "metadata": {"order_id": "1"},
            "webhook_url": "https://example.com/webhook",
        },
    )
    assert conflict_response.status_code == 409

    read_response = await client.get(
        f"/api/v1/payments/{payment_id}",
        headers={"X-API-Key": "test-api-key"},
    )
    assert read_response.status_code == 200
    assert read_response.json()["id"] == str(payment_id)


@pytest.mark.asyncio
async def test_api_key_is_required(client: httpx.AsyncClient) -> None:
    """Reject requests without the static API key."""
    response = await client.get("/api/v1/payments/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_payment_returns_not_found(
    client: httpx.AsyncClient,
    clean_database: None,
) -> None:
    """Return HTTP 404 for a payment that does not exist."""
    response = await client.get(
        "/api/v1/payments/00000000-0000-0000-0000-000000000000",
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 404
