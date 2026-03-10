import os

import pytest

import payments_ledger.api.auth as auth_api
from payments_ledger.services.auth import InvalidCredentials
from payments_ledger.adapters.db.ledger_repo import SqlAlchemyLedgerRepo
from payments_ledger.ledger_domain.ledger_engine import EntryType


def _expected_balance_not_found(account_id: str, currency: str, request_id: str) -> dict[str, str]:
    payload = {
        "account_id": account_id,
        "currency": currency,
        "status": "FAILED",
        "request_id": request_id,
        "error_code": "ACCOUNT_NOT_FOUND",
    }
    if os.getenv("PAYMENTS_DEBUG_ERRORS", "0") == "1":
        payload["error_message"] = "Account Not Found"
    return payload


@pytest.mark.asyncio
async def test_balance_success_contract(
    api_client, db_session, seed_client_account, seed_ledger_entries
):
    await seed_client_account(db_session, account_id="acc_1")
    await seed_ledger_entries(db_session)

    response = await api_client.get(
        "/balance/acc_1?currency=EUR",
        headers={"X-Request-Id": "req-bal-ok"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "account_id": "acc_1",
        "currency": "EUR",
        "balance": -100,
        "status": "OK",
        "request_id": "req-bal-ok",
    }


@pytest.mark.asyncio
async def test_balance_zero_when_no_entries_contract(api_client, db_session, seed_client_account):
    await seed_client_account(db_session, account_id="acc_zero")

    response = await api_client.get(
        "/balance/acc_zero?currency=EUR",
        headers={"X-Request-Id": "req-bal-zero"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "account_id": "acc_zero",
        "currency": "EUR",
        "balance": 0,
        "status": "OK",
        "request_id": "req-bal-zero",
    }


@pytest.mark.asyncio
async def test_balance_not_found_error_contract(api_client):
    response = await api_client.get(
        "/balance/missing?currency=EUR",
        headers={"X-Request-Id": "req-bal-missing"},
    )

    assert response.status_code == 200
    assert response.json() == _expected_balance_not_found(
        account_id="missing",
        currency="EUR",
        request_id="req-bal-missing",
    )


@pytest.mark.asyncio
async def test_balance_foreign_account_error_contract(api_client, db_session, seed_client_account):
    await seed_client_account(db_session, client_id="client_2", account_id="acc_foreign")

    response = await api_client.get(
        "/balance/acc_foreign?currency=EUR",
        headers={"X-Request-Id": "req-bal-foreign"},
    )

    assert response.status_code == 200
    assert response.json() == _expected_balance_not_found(
        account_id="acc_foreign",
        currency="EUR",
        request_id="req-bal-foreign",
    )


@pytest.mark.asyncio
async def test_balance_generates_request_id_when_header_missing(api_client):
    response = await api_client.get("/balance/missing?currency=EUR")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert data["error_code"] == "ACCOUNT_NOT_FOUND"
    assert data["account_id"] == "missing"
    assert data["currency"] == "EUR"
    assert isinstance(data["request_id"], str)
    assert data["request_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("currency", ["EU", "EURO"])
async def test_balance_invalid_currency_returns_422(raw_api_client, currency):
    response = await raw_api_client.get(f"/balance/acc_1?currency={currency}")

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(err["loc"] == ["query", "currency"] for err in errors)


@pytest.mark.asyncio
async def test_balance_missing_authorization_returns_422(raw_api_client):
    response = await raw_api_client.get("/balance/acc_1?currency=EUR")

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(err["loc"] == ["header", "authorization"] for err in errors)


@pytest.mark.asyncio
async def test_balance_non_bearer_authorization_returns_401(raw_api_client):
    response = await raw_api_client.get(
        "/balance/acc_1?currency=EUR",
        headers={"Authorization": "Basic dGVzdDp0ZXN0"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing bearer token"}


@pytest.mark.asyncio
async def test_balance_invalid_api_key_returns_401(raw_api_client, monkeypatch):
    async def _fake_authenticate_token(_repo, _token):
        raise InvalidCredentials("Invalid api key")

    monkeypatch.setattr(auth_api, "authenticate_token", _fake_authenticate_token)

    response = await raw_api_client.get(
        "/balance/acc_1?currency=EUR",
        headers={"Authorization": "Bearer bad-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "INVALID_API_KEY"}


@pytest.mark.asyncio
async def test_balance_second_read_uses_cache_hit(
    api_client,
    db_session,
    seed_client_account,
    seed_ledger_entries,
    monkeypatch,
):
    await seed_client_account(
        db_session,
        account_id="acc_cache_hit",
        ledger_version=2,
    )
    await seed_ledger_entries(
        db_session,
        entries=[
            {
                "account_id": "acc_cache_hit",
                "ledger_version": 1,
                "amount": -150,
                "currency": "EUR",
                "entry_type": EntryType.DEBIT,
                "request_id": "r1",
            },
            {
                "account_id": "acc_cache_hit",
                "ledger_version": 2,
                "amount": 50,
                "currency": "EUR",
                "entry_type": EntryType.CREDIT,
                "request_id": "r2",
            },
        ],
    )

    response_1 = await api_client.get(
        "/balance/acc_cache_hit?currency=EUR",
        headers={"X-Request-Id": "req-cache-1"},
    )

    assert response_1.status_code == 200
    assert response_1.json()["balance"] == -100

    async def _boom(_self, _account_id: str, _currency: str) -> int:
        raise AssertionError("DB get_balance should not be called on cache hit")

    monkeypatch.setattr(SqlAlchemyLedgerRepo, "get_balance", _boom)

    response_2 = await api_client.get(
        "/balance/acc_cache_hit?currency=EUR",
        headers={"X-Request-Id": "req-cache-2"},
    )

    assert response_2.status_code == 200
    assert response_2.json()["balance"] == -100
    assert response_2.json()["status"] == "OK"
