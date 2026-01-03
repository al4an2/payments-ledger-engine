from fastapi import FastAPI, Header, Depends
from pydantic import BaseModel, Field
from uuid import uuid4
from payments_ledger.api.auth import get_client_id

from payments_ledger.config.logging import logger
from src.payments_ledger.services.idempotency import handle_payment

app = FastAPI()

class PaymentRequest(BaseModel):
    account_id: str
    amount: int = Field(..., description="minor units, positive")
    currency: str = Field(..., min_length=3, max_length=3)
    request_id: str | None = None

class PaymentResponse(BaseModel):
    payment_id: str
    status: str
    request_id: str
    error_code: str | None = None
    error_message: str | None = None

@app.get("/health")
async def read_root():
    return {"Hello": "World"}

@app.get("/balance/{account_id}")
async def read_root():
    return {"Hello": "World"}


@app.post("/payments", response_model=PaymentResponse, response_model_exclude_none=True)
async def create_payment( payload: PaymentRequest,  idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    logger.info("payment_request", extra={"account_id": payload.account_id})
    request_id = payload.request_id or str(uuid4())
    signed_amount = payload.amount

    handle_payment(payload.cli)

    response = PaymentResponse(
        payment_id=str(uuid4()), #tmp generate
        status="COMPLETED",
        request_id=request_id
    )
    return response