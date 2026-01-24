from fastapi import FastAPI, Request, Header, Depends
from fastapi.responses import JSONResponse
from uuid import uuid4
from payments_ledger.api.auth import get_client_id

from payments_ledger.config.logging import logger
from payments_ledger.api.schemas import PaymentRequest, PaymentResponse
from payments_ledger.services.ports import IdempotencyConflict, IdempotencyInProgress, UnitOfWork
from payments_ledger.services.payments import process_payment, InvalidDirection
from payments_ledger.db.session import get_session_factory
from payments_ledger.adapters.db.uow import SqlAlchemyUnitOfWork

app = FastAPI()


def get_uow():
    return SqlAlchemyUnitOfWork(get_session_factory())


@app.exception_handler(IdempotencyConflict)
async def handle_idempotency_conflict(request: Request, exc: IdempotencyConflict):
    return JSONResponse(status_code=409, content={"detail": exc.code})


@app.exception_handler(IdempotencyInProgress)
async def handle_idempotency_in_progress(request: Request, exc: IdempotencyInProgress):
    return JSONResponse(status_code=409, content={"detail": exc.code})


@app.exception_handler(InvalidDirection)
async def handle_invalid_direction(request: Request, exc: InvalidDirection):
    return JSONResponse(status_code=422, content={"detail": exc.code})


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "INTERNAL_ERROR"})


@app.get("/health")
async def read_root():
    return {"Hello": "200"}


@app.get("/balance/{account_id}")
async def read_balance():
    return {"Hello": "Get your balance"}


@app.post("/payments", response_model=PaymentResponse, response_model_exclude_none=True)
async def create_payment(
    payload: PaymentRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    client_id: str = Depends(get_client_id),
    uow: UnitOfWork = Depends(get_uow),
):
    request_id = payload.request_id or str(uuid4())
    logger.info(
        "payment_request", extra={"account_id": payload.account_id, "request_id": request_id}
    )
    #    signed_amount = payload.amount

    result = await process_payment(
        uow=uow,
        client_id=client_id,
        idempotency_key=idempotency_key,
        payload=payload.model_dump(exclude_none=True),
        request_id=request_id,
    )

    return PaymentResponse(**result)
