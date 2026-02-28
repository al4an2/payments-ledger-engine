import os

import pytest
from httpx import AsyncClient, ASGITransport

import payments_ledger.api.auth as auth_api
import payments_ledger.api.main as main_api
from payments_ledger.adapters.db.idempotency_repo import SqlAlchemyIdempotencyRepo
from payments_ledger.ledger_domain.ledger_engine import BalanceType
from payments_ledger.services.auth import InvalidCredentials
from payments_ledger.services.idempotency import make_request_hash, reserve_idempotency
from payments_ledger.services.ports import IdempotencyInProgress


def _expected_payment_failed(
    request_id: str, error_code: str, error_message: str
) -> dict[str, str]:
    payload = {
        "status": "FAILED",
        "request_id": request_id,
        "error_code": error_code,
    }
    if os.getenv("PAYMENTS_DEBUG_ERRORS", "0") == "1":
        payload["error_message"] = error_message
    return payload


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


@pytest.mark.asyncio
async def test_payments_idempotency_conflict_409(api_client, db_session, seed_client_account):
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
            idem_key="idem-conflict-001",
            request_hash=request_hash,
        )
        assert reserved.state == "reserved"

    payload_2 = {
        "account_id": "acc_1",
        "amount": 900,
        "currency": "EUR",
        "direction": "DEBIT",
        "request_id": "req-2",
    }
    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-conflict-001"},
        json=payload_2,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "IDEMPOTENCY_CONFLICT"}


@pytest.mark.asyncio
async def test_payments_missing_idempotency_key_returns_422(api_client):
    response = await api_client.post(
        "/payments",
        json={
            "account_id": "acc_1",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-no-idem",
        },
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(err["loc"] == ["header", "Idempotency-Key"] for err in errors)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_key",
    [
        "short-1",  # < 8 chars
        "k" * 129,  # > 128 chars
        "invalid key!",  # invalid symbols
    ],
)
async def test_payments_invalid_idempotency_key_returns_422(api_client, invalid_key):
    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": invalid_key},
        json={
            "account_id": "acc_1",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-invalid-idem-1",
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "INVALID_IDEMPOTENCY_KEY"}


@pytest.mark.asyncio
async def test_payments_idempotency_duplicate_returns_same_response(
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
        "request_id": "req-dup-1",
    }

    response_1 = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-duplicate-001"},
        json=payload,
    )
    response_2 = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-duplicate-001"},
        json=payload,
    )

    assert response_1.status_code == 200
    assert response_2.status_code == 200

    data_1 = response_1.json()
    data_2 = response_2.json()
    assert data_1["status"] == "COMPLETED"
    assert data_2["status"] == "COMPLETED"
    assert data_1["payment_id"] == data_2["payment_id"]
    assert data_1["request_id"] == data_2["request_id"]


@pytest.mark.asyncio
async def test_payments_idempotency_completed_conflict_returns_409(
    api_client, db_session, seed_client_account
):
    await seed_client_account(
        db_session,
        account_id="acc_1",
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=2000,
    )

    payload_1 = {
        "account_id": "acc_1",
        "amount": 1000,
        "currency": "EUR",
        "direction": "DEBIT",
        "request_id": "req-first-1",
    }
    payload_2 = {
        "account_id": "acc_1",
        "amount": 900,
        "currency": "EUR",
        "direction": "DEBIT",
        "request_id": "req-second-1",
    }

    response_1 = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-completed-conflict-001"},
        json=payload_1,
    )
    response_2 = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-completed-conflict-001"},
        json=payload_2,
    )

    assert response_1.status_code == 200
    assert response_1.json()["status"] == "COMPLETED"
    assert response_2.status_code == 409
    assert response_2.json() == {"detail": "IDEMPOTENCY_CONFLICT"}


@pytest.mark.asyncio
async def test_payments_idempotency_duplicate_failed_returns_same_response(
    api_client, db_session, seed_client_account
):
    await seed_client_account(db_session, account_id="existing_acc")

    payload = {
        "account_id": "missing_acc",
        "amount": 1000,
        "currency": "EUR",
        "direction": "DEBIT",
        "request_id": "req-failed-dup-1",
    }

    response_1 = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-failed-duplicate-001"},
        json=payload,
    )
    response_2 = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-failed-duplicate-001"},
        json=payload,
    )

    assert response_1.status_code == 200
    assert response_2.status_code == 200

    data_1 = response_1.json()
    data_2 = response_2.json()
    assert data_1["status"] == "FAILED"
    assert data_1["error_code"] == "ACCOUNT_NOT_FOUND"
    assert "payment_id" not in data_1
    assert "payment_id" not in data_2
    assert data_2 == data_1


@pytest.mark.asyncio
async def test_payments_invalid_direction_in_body_422(api_client):
    payload = {
        "account_id": "invalid_dir_acc",
        "amount": 1000,
        "currency": "EUR",
        "direction": "WRONG",
        "request_id": "req-invalid-dir-1",
    }

    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-invalid-dir-001"},
        json=payload,
    )

    assert response.status_code == 422
    data = response.json()
    assert isinstance(data.get("detail"), list)
    assert any(err.get("loc") == ["body", "direction"] for err in data["detail"])


@pytest.mark.asyncio
async def test_payments_account_not_found_returns_failed(
    api_client, db_session, seed_client_account
):
    await seed_client_account(db_session, account_id="acc_existing")

    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-account-not-found-001"},
        json={
            "account_id": "missing_acc",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-pay-missing-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == _expected_payment_failed(
        request_id="req-pay-missing-1",
        error_code="ACCOUNT_NOT_FOUND",
        error_message="Account Not Found",
    )


@pytest.mark.asyncio
async def test_payments_foreign_account_returns_failed(api_client, db_session, seed_client_account):
    await seed_client_account(db_session, client_id="client_1", account_id="acc_own")
    await seed_client_account(db_session, client_id="client_2", account_id="acc_foreign")

    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-foreign-account-001"},
        json={
            "account_id": "acc_foreign",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-pay-foreign-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == _expected_payment_failed(
        request_id="req-pay-foreign-1",
        error_code="ACCOUNT_NOT_FOUND",
        error_message="Account Not Found",
    )


@pytest.mark.asyncio
async def test_payments_insufficient_funds_debit_only_returns_failed(
    api_client, db_session, seed_client_account
):
    await seed_client_account(db_session, account_id="acc_debit_only")

    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-insufficient-funds-001"},
        json={
            "account_id": "acc_debit_only",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-insufficient-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == _expected_payment_failed(
        request_id="req-insufficient-1",
        error_code="INSUFFICIENT_FUNDS",
        error_message="Not enough funds to debit operation",
    )


@pytest.mark.asyncio
async def test_payments_credit_limit_exceeded_returns_failed(
    api_client, db_session, seed_client_account
):
    await seed_client_account(
        db_session,
        account_id="acc_credit_limited",
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=500,
    )

    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-credit-limit-001"},
        json={
            "account_id": "acc_credit_limited",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-credit-limit-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == _expected_payment_failed(
        request_id="req-credit-limit-1",
        error_code="CREDIT_LIMIT_EXCEEDED",
        error_message="Credit limit exceeded",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("amount", "idem_suffix"),
    [
        (0, "zero"),
        (-100, "negative"),
    ],
)
async def test_payments_invalid_amount_returns_failed(
    api_client, db_session, seed_client_account, amount, idem_suffix
):
    await seed_client_account(db_session, account_id="acc_invalid_amount")

    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": f"idem-invalid-amount-{idem_suffix}-001"},
        json={
            "account_id": "acc_invalid_amount",
            "amount": amount,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": f"req-invalid-amount-{idem_suffix}-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == _expected_payment_failed(
        request_id=f"req-invalid-amount-{idem_suffix}-1",
        error_code="INVALID_AMOUNT",
        error_message="Not valid amount to debit/credit",
    )


@pytest.mark.asyncio
async def test_payments_missing_authorization_returns_422(raw_api_client):
    response = await raw_api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-missing-auth-001"},
        json={
            "account_id": "acc_1",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-missing-auth-1",
        },
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(err["loc"] == ["header", "authorization"] for err in errors)


@pytest.mark.asyncio
async def test_payments_non_bearer_authorization_returns_401(raw_api_client):
    response = await raw_api_client.post(
        "/payments",
        headers={
            "Authorization": "Basic dGVzdDp0ZXN0",
            "Idempotency-Key": "idem-non-bearer-001",
        },
        json={
            "account_id": "acc_1",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-non-bearer-1",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing bearer token"}


@pytest.mark.asyncio
async def test_payments_invalid_api_key_returns_401(raw_api_client, monkeypatch):
    async def _fake_authenticate_token(_repo, _token):
        raise InvalidCredentials("Invalid api key")

    monkeypatch.setattr(auth_api, "authenticate_token", _fake_authenticate_token)

    response = await raw_api_client.post(
        "/payments",
        headers={
            "Authorization": "Bearer bad-token",
            "Idempotency-Key": "idem-invalid-api-key-001",
        },
        json={
            "account_id": "acc_1",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-invalid-api-key-1",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "INVALID_API_KEY"}


@pytest.mark.asyncio
async def test_payments_unexpected_exception_mapping_returns_500(monkeypatch):
    async def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    async def _fake_authenticate_token(_repo, _token):
        return "client_1"

    monkeypatch.setattr(main_api, "process_payment", _boom)
    monkeypatch.setattr(auth_api, "authenticate_token", _fake_authenticate_token)

    transport = ASGITransport(app=main_api.app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/payments",
            headers={
                "Authorization": "Bearer token-for-test",
                "Idempotency-Key": "idem-unexpected-500-001",
            },
            json={
                "account_id": "acc_1",
                "amount": 1000,
                "currency": "EUR",
                "direction": "DEBIT",
                "request_id": "req-unexpected-1",
            },
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "INTERNAL_ERROR"}


@pytest.mark.asyncio
async def test_payments_in_progress_exception_mapping_returns_409(api_client, monkeypatch):
    async def _in_progress(*_args, **_kwargs):
        raise IdempotencyInProgress()

    monkeypatch.setattr(main_api, "process_payment", _in_progress)

    response = await api_client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-in-progress-handler-001"},
        json={
            "account_id": "acc_1",
            "amount": 1000,
            "currency": "EUR",
            "direction": "DEBIT",
            "request_id": "req-in-progress-handler-1",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "IDEMPOTENCY_IN_PROGRESS"}
