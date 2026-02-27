import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from payments_ledger.adapters.db.uow import SqlAlchemyUnitOfWork
from payments_ledger.services.payments import process_payment
from payments_ledger.services.ports import PaymentCommand
from payments_ledger.ledger_domain.ledger_engine import BalanceType


@pytest.mark.asyncio
async def test_process_payment_duplicate_returns_same_response(
    db_session, async_engine, seed_client, seed_account
):
    await seed_client(db_session)
    await seed_account(
        db_session,
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=2000,
    )

    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    uow = SqlAlchemyUnitOfWork(session_factory)
    payload = PaymentCommand(
        account_id="acc_1",
        amount=1000,
        currency="EUR",
        direction="DEBIT",
        request_id="r1",
    )

    result_1 = await process_payment(
        uow=uow,
        client_id="client_1",
        idempotency_key="idem-10",
        payload=payload,
        request_id="r1",
    )
    result_2 = await process_payment(
        uow=uow,
        client_id="client_1",
        idempotency_key="idem-10",
        payload=payload,
        request_id="r2",
    )

    assert result_1["payment_id"] == result_2["payment_id"]
    assert result_1["status"] == "COMPLETED"
    assert result_2["status"] == "COMPLETED"
