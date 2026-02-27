import pytest

from payments_ledger.adapters.db.idempotency_repo import SqlAlchemyIdempotencyRepo
from payments_ledger.ledger_domain.ledger_engine import BalanceType
from payments_ledger.services.idempotency import make_request_hash, reserve_idempotency


@pytest.mark.asyncio
async def test_payments_contract(api_client, db_session, seed_client_account):
    await seed_client_account(
        db_session,
        account_id="acc_1",
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=2000,
    )

    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-001"},
        json={
            "account_id": "acc_1",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-1",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["request_id"] == "req-1"
    assert data["payment_id"]
    assert isinstance(data["payment_id"], str)
    assert "error_code" not in data
    assert "error_message" not in data


@pytest.mark.asyncio
async def test_payments_request_id_generation(api_client, db_session, seed_client_account):
    await seed_client_account(
        db_session,
        account_id="acc_1",
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=2000,
    )

    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-reqid-001"},
        json={
            "account_id": "acc_1",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["request_id"]
    assert isinstance(data["request_id"], str)
    assert data["payment_id"]
    assert isinstance(data["payment_id"], str)
    assert "error_code" not in data
    assert "error_message" not in data


@pytest.mark.asyncio
async def test_payments_idempotency_in_progress_returns_409(
    api_client, db_session, seed_client_account
):
    await seed_client_account(
        db_session,
        account_id="acc_1",
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=2000,
    )

    payload = {
        "account_id": "acc_1",
        "amount": 1000,
        "currency": "EUR",
        "direction": "DEBIT",
        "request_id": "req-1",
    }

    repo = SqlAlchemyIdempotencyRepo(db_session)
    request_hash = make_request_hash(payload)
    async with db_session.begin():
        reserved = await reserve_idempotency(
            repo,
            client_id="client_1",
            idem_key="idem-in-progress-001",
            request_hash=request_hash,
        )
        assert reserved.state == "reserved"

    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-in-progress-001"},
        json=payload,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "IDEMPOTENCY_IN_PROGRESS"}
