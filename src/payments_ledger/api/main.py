from fastapi import FastAPI, Request, Header, Depends
from fastapi.responses import JSONResponse
from uuid import uuid4
from payments_ledger.api.auth import get_client_id

from payments_ledger.config.logging import logger
from payments_ledger.api.schemas import PaymentRequest, PaymentResponse
from payments_ledger.services.ports import IdempotencyConflict, IdempotencyInProgress, UnitOfWork
from payments_ledger.services.payments import process_payment
from payments_ledger.db.session import get_session_factory
from payments_ledger.adapters.db.uow import SqlAlchemyUnitOfWork
from payments_ledger.services.ports import PaymentCommand

app = FastAPI()


def get_uow():
    return SqlAlchemyUnitOfWork(get_session_factory())


@app.exception_handler(IdempotencyConflict)
async def handle_idempotency_conflict(request: Request, exc: IdempotencyConflict):
    logger.warning(
        "idempotency_conflict",
        extra={
            "path": request.url.path,
            "error_code": exc.code,
        },
    )
    return JSONResponse(status_code=409, content={"detail": exc.code})


@app.exception_handler(IdempotencyInProgress)
async def handle_idempotency_in_progress(request: Request, exc: IdempotencyInProgress):
    logger.warning(
        "idempotency_in_progress",
        extra={
            "path": request.url.path,
            "error_code": exc.code,
        },
    )
    return JSONResponse(status_code=409, content={"detail": exc.code})


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception):
    logger.exception("unhandled_exception", extra={"path": request.url.path})
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

    payload_cmd = PaymentCommand(
        account_id=payload.account_id,
        amount=payload.amount,
        currency=payload.currency,
        direction=payload.direction,
        request_id=request_id,
    )

    logger.info(
        "payment_request",
        extra={
            "request_id": request_id,
            "client_id": client_id,
            "account_id": payload.account_id,
            "idempotency_key": idempotency_key,
        },
    )

    result = await process_payment(
        uow=uow,
        client_id=client_id,
        idempotency_key=idempotency_key,
        payload=payload_cmd,
        request_id=request_id,
    )

    logger.info(
        "payment_result",
        extra={
            "request_id": request_id,
            "status": result["status"],
            "error_code": result.get("error_code"),
        },
    )

    return PaymentResponse(**result)
