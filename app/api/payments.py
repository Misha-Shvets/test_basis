"""Payment HTTP endpoints."""

from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Depends, Header, HTTPException, status

from api.auth import require_api_key
from api.models import CreatePaymentRequest, PaymentResponse
from payment.errors import (
    IdempotencyConflictError,
    PaymentError,
    PaymentNotFoundError,
)
from payment.services import PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    route_class=DishkaRoute,
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_payment(
    request: CreatePaymentRequest,
    service: FromDishka[PaymentService],
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> PaymentResponse:
    """Create a payment."""
    try:
        payment = await service.create(
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            metadata=request.metadata,
            webhook_url=str(request.webhook_url),
            idempotency_key=idempotency_key,
        )
    except IdempotencyConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except PaymentError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return PaymentResponse.from_domain(payment)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    service: FromDishka[PaymentService],
) -> PaymentResponse:
    """Get a payment."""
    try:
        payment = await service.get_or_raise(payment_id)
    except PaymentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return PaymentResponse.from_domain(payment)
