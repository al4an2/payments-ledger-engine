import pytest
from payments_ledger.ledger_domain.ledger_engine import BalanceType


@pytest.mark.asyncio
async def test_account_info_ok(api_client, db_session, seed_client_account):
    await seed_client_account(db_session, account_id="acc_1")

    response = await api_client.get(
        "/accounts/acc_1",
        headers={"X-Request-Id": "req-acc-1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["account_id"] == "acc_1"
    assert data["balance_type"] == "DEBIT_ONLY"
    assert data["request_id"] == "req-acc-1"
    assert "error_code" not in data
    assert "error_message" not in data


@pytest.mark.asyncio
async def test_account_info_not_found_returns_failed(api_client):
    response = await api_client.get("/accounts/missing")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert data["error_code"] == "ACCOUNT_NOT_FOUND"
    assert data["request_id"]


@pytest.mark.asyncio
async def test_account_info_foreign_account_returns_failed(
    api_client, db_session, seed_client_account
):
    await seed_client_account(
        db_session,
        client_id="client_2",
        account_id="acc_foreign",
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=5000,
    )

    response = await api_client.get(
        "/accounts/acc_foreign",
        headers={"X-Request-Id": "req-acc-foreign"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert data["error_code"] == "ACCOUNT_NOT_FOUND"
    assert data["account_id"] == "acc_foreign"
    assert data["request_id"] == "req-acc-foreign"
    assert "balance_type" not in data
    assert "credit_limit" not in data
