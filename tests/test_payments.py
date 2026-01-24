import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from payments_ledger.api.schemas import PaymentRequest
from payments_ledger.data_models.db_models import Client, Account
from payments_ledger.adapters.db.uow import SqlAlchemyUnitOfWork
from payments_ledger.services.payments import (
    process_payment,
    _types_direction,
    InvalidDirection,
)
from payments_ledger.ledger_domain.ledger_engine import EntryType, BalanceType


async def _seed_client(session, client_id: str = "client_1") -> None:
    session.add(Client(client_id=client_id, name="Test Client", api_key_hash="hash_1"))
    await session.commit()


async def _seed_account(
    session,
    client_id: str = "client_1",
    account_id: str = "acc_1",
    balance_type: BalanceType = BalanceType.DEBIT_ONLY,
    credit_limit: int | None = None,
    ledger_version: int = 0,
) -> None:
    session.add(
        Account(
            account_id=account_id,
            client_id=client_id,
            balance_type=balance_type,
            credit_limit=credit_limit,
            ledger_version=ledger_version,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_process_payment_duplicate_returns_same_response(db_session, async_engine):
    await _seed_client(db_session)
    await _seed_account(
        db_session,
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=2000,
    )

    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    uow = SqlAlchemyUnitOfWork(session_factory)
    payload = PaymentRequest(
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


def test_types_direction_valid():
    assert _types_direction("DEBIT") == EntryType.DEBIT
    assert _types_direction("CREDIT") == EntryType.CREDIT


def test_types_direction_invalid():
    with pytest.raises(InvalidDirection):
        _types_direction("REFUND")
