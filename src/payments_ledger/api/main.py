from fastapi import FastAPI, Header, Depends
from uuid import uuid4
from payments_ledger.api.auth import get_client_id
from payments_ledger.db.session import get_session

from payments_ledger.config.logging import logger
from payments_ledger.services.idempotency import reserve_idempotency
from payments_ledger.services.idempotency import make_request_hash
from payments_ledger.api.schemas import PaymentRequest, PaymentResponse

app = FastAPI()



@app.get("/health")
async def read_root():
    return {"Hello": "World"}

@app.get("/balance/{account_id}")
async def read_balance():
    return {"Hello": "World"}


@app.post("/payments", response_model=PaymentResponse, response_model_exclude_none=True)
async def create_payment(
    payload: PaymentRequest,  
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    client_id: str = Depends(get_client_id),
    session = Depends(get_session),
):
    logger.info("payment_request", extra={"account_id": payload.account_id})
    request_id = payload.request_id or str(uuid4())
#    signed_amount = payload.amount

    request_hash = make_request_hash(payload)

    await reserve_idempotency(session=session,
    client_id=client_id,
    idem_key=idempotency_key,
    request_hash=request_hash)

    response = PaymentResponse(
        payment_id=str(uuid4()), #tmp generate
        status="COMPLETED",
        request_id=request_id
    )
    return response