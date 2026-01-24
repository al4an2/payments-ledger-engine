import pytest

from payments_ledger.api.schemas import PaymentRequest
from payments_ledger.data_models.db_models import Client
from payments_ledger.adapters.db.idempotency_repo import SqlAlchemyIdempotencyRepo
from payments_ledger.services.idempotency import (
    complete_idempotency,
    make_request_hash,
    reserve_idempotency,
)
from payments_ledger.services.ports import IdempotencyConflict, IdempotencyInProgress


async def _seed_client(session, client_id: str = "client_1") -> None:
    session.add(Client(client_id=client_id, name="Test Client", api_key_hash="hash_1"))
    await session.commit()


def test_make_request_hash_excludes_request_id():
    req_a = PaymentRequest(account_id="acc_1", amount=1000, currency="EUR", request_id="r1")
    req_b = PaymentRequest(account_id="acc_1", amount=1000, currency="EUR", request_id="r2")
    assert make_request_hash(req_a.model_dump(exclude_none=True)) == make_request_hash(
        req_b.model_dump(exclude_none=True)
    )


@pytest.mark.asyncio
async def test_idempotency_duplicate_returns_saved_response(db_session):
    await _seed_client(db_session)

    repo = SqlAlchemyIdempotencyRepo(db_session)
    payload = PaymentRequest(account_id="acc_1", amount=1000, currency="EUR", request_id="r1")
    request_hash = make_request_hash(payload.model_dump(exclude_none=True))
    response = {"payment_id": "p1", "status": "COMPLETED", "request_id": "r1"}

    async with db_session.begin():
        result = await reserve_idempotency(repo, "client_1", "idem-1", request_hash)
        assert result.state == "reserved"

    async with db_session.begin():
        await complete_idempotency(repo, "client_1", "idem-1", response)

    async with db_session.begin():
        dup = await reserve_idempotency(repo, "client_1", "idem-1", request_hash)
        assert dup.state == "duplicate"
        assert dup.response == response


@pytest.mark.asyncio
async def test_idempotency_in_progress_raises(db_session):
    await _seed_client(db_session)

    repo = SqlAlchemyIdempotencyRepo(db_session)
    payload = PaymentRequest(account_id="acc_1", amount=1000, currency="EUR")
    request_hash = make_request_hash(payload.model_dump(exclude_none=True))

    async with db_session.begin():
        result = await reserve_idempotency(repo, "client_1", "idem-2", request_hash)
        assert result.state == "reserved"

    async with db_session.begin():
        with pytest.raises(IdempotencyInProgress):
            await reserve_idempotency(repo, "client_1", "idem-2", request_hash)


@pytest.mark.asyncio
async def test_idempotency_conflict_raises(db_session):
    await _seed_client(db_session)

    repo = SqlAlchemyIdempotencyRepo(db_session)
    payload = PaymentRequest(account_id="acc_1", amount=1000, currency="EUR")
    request_hash = make_request_hash(payload.model_dump(exclude_none=True))
    response = {"payment_id": "p1", "status": "COMPLETED", "request_id": "r1"}

    async with db_session.begin():
        await reserve_idempotency(repo, "client_1", "idem-3", request_hash)

    async with db_session.begin():
        await complete_idempotency(repo, "client_1", "idem-3", response)

    payload_2 = PaymentRequest(account_id="acc_1", amount=2000, currency="EUR")
    request_hash_2 = make_request_hash(payload_2.model_dump(exclude_none=True))

    async with db_session.begin():
        with pytest.raises(IdempotencyConflict):
            await reserve_idempotency(repo, "client_1", "idem-3", request_hash_2)
