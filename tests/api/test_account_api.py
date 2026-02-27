import os

import pytest

import payments_ledger.api.auth as auth_api
from payments_ledger.services.auth import InvalidCredentials
from payments_ledger.ledger_domain.ledger_engine import BalanceType


def _expected_account_not_found(account_id: str, request_id: str) -> dict[str, str]:
    payload = {
        "account_id": account_id,
        "status": "FAILED",
        "request_id": request_id,
        "error_code": "ACCOUNT_NOT_FOUND",
    }
    if os.getenv("PAYMENTS_DEBUG_ERRORS", "0") == "1":
        payload["error_message"] = "Account Not Found"
    return payload


@pytest.mark.asyncio
async def test_account_info_debit_only_success_contract(
    api_client, db_session, seed_client_account
):
    await seed_client_account(db_session, account_id="acc_debit")

    response = await api_client.get(
        "/accounts/acc_debit",
        headers={"X-Request-Id": "req-acc-debit"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "account_id": "acc_debit",
        "balance_type": "DEBIT_ONLY",
        "status": "OK",
        "request_id": "req-acc-debit",
    }


@pytest.mark.asyncio
async def test_account_info_credit_allowed_success_contract(
    api_client, db_session, seed_client_account
):
    await seed_client_account(
        db_session,
        account_id="acc_credit",
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=5000,
    )

    response = await api_client.get(
        "/accounts/acc_credit",
        headers={"X-Request-Id": "req-acc-credit"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "account_id": "acc_credit",
        "balance_type": "CREDIT_ALLOWED",
        "credit_limit": 5000,
        "status": "OK",
        "request_id": "req-acc-credit",
    }


@pytest.mark.asyncio
async def test_account_info_not_found_error_contract(api_client):
    response = await api_client.get(
        "/accounts/missing",
        headers={"X-Request-Id": "req-acc-missing"},
    )

    assert response.status_code == 200
    assert response.json() == _expected_account_not_found("missing", "req-acc-missing")


@pytest.mark.asyncio
async def test_account_info_foreign_account_error_contract(
    api_client, db_session, seed_client_account
):
    await seed_client_account(
        db_session,
        client_id="client_2",
        account_id="acc_foreign",
    )

    response = await api_client.get(
        "/accounts/acc_foreign",
        headers={"X-Request-Id": "req-acc-foreign"},
    )

    assert response.status_code == 200
    assert response.json() == _expected_account_not_found("acc_foreign", "req-acc-foreign")


@pytest.mark.asyncio
async def test_account_info_generates_request_id_when_header_missing(
    api_client, db_session, seed_client_account
):
    await seed_client_account(db_session, account_id="acc_1")

    response = await api_client.get("/accounts/acc_1")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["account_id"] == "acc_1"
    assert data["balance_type"] == "DEBIT_ONLY"
    assert isinstance(data["request_id"], str)
    assert data["request_id"]


@pytest.mark.asyncio
async def test_account_info_empty_account_id_returns_404(raw_api_client):
    response = await raw_api_client.get("/accounts/")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_account_info_missing_authorization_returns_422(raw_api_client):
    response = await raw_api_client.get("/accounts/acc_1")

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(err["loc"] == ["header", "authorization"] for err in errors)


@pytest.mark.asyncio
async def test_account_info_non_bearer_authorization_returns_401(raw_api_client):
    response = await raw_api_client.get(
        "/accounts/acc_1",
        headers={"Authorization": "Basic dGVzdDp0ZXN0"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing bearer token"}


@pytest.mark.asyncio
async def test_account_info_invalid_api_key_returns_401(raw_api_client, monkeypatch):
    async def _fake_authenticate_token(_repo, _token):
        raise InvalidCredentials("Invalid api key")

    monkeypatch.setattr(auth_api, "authenticate_token", _fake_authenticate_token)

    response = await raw_api_client.get(
        "/accounts/acc_1",
        headers={"Authorization": "Bearer bad-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "INVALID_API_KEY"}
