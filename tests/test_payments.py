import pytest

from payments_ledger.api.schemas import PaymentRequest
from payments_ledger.data_models.db_models import Client
from payments_ledger.adapters.db.idempotency_repo import SqlAlchemyIdempotencyRepo
from payments_ledger.services.payments import process_payment


async def _seed_client(session, client_id: str = "client_1") -> None:
    session.add(Client(client_id=client_id, name="Test Client", api_key_hash="hash_1"))
    await session.commit()


@pytest.mark.asyncio
async def test_process_payment_duplicate_returns_same_response(db_session):
    await _seed_client(db_session)

    idempotency_repo = SqlAlchemyIdempotencyRepo(db_session)
    payload = PaymentRequest(account_id="acc_1", amount=1000, currency="EUR", request_id="r1")

    result_1 = await process_payment(
        idempotency_repo=idempotency_repo,
        session=db_session,
        client_id="client_1",
        idempotency_key="idem-10",
        payload=payload,
        request_id="r1",
    )
    result_2 = await process_payment(
        idempotency_repo=idempotency_repo,
        session=db_session,
        client_id="client_1",
        idempotency_key="idem-10",
        payload=payload,
        request_id="r2",
    )

    assert result_1["payment_id"] == result_2["payment_id"]
    assert result_1["status"] == "COMPLETED"
    assert result_2["status"] == "COMPLETED"
