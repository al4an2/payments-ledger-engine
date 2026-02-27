import pytest


@pytest.mark.asyncio
async def test_balance_ok(api_client, db_session, seed_client_account, seed_ledger_entries):
    await seed_client_account(db_session)
    await seed_ledger_entries(db_session)

    response = await api_client.get(
        "/balance/acc_1?currency=EUR",
        headers={"X-Request-Id": "req-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["balance"] == -100
    assert data["currency"] == "EUR"
    assert data["account_id"] == "acc_1"
    assert data["request_id"] == "req-1"


@pytest.mark.asyncio
async def test_balance_account_not_found(api_client):
    response = await api_client.get("/balance/missing?currency=EUR")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert data["error_code"] == "ACCOUNT_NOT_FOUND"
    assert data["request_id"]


@pytest.mark.asyncio
async def test_balance_invalid_currency_returns_422(api_client):
    response = await api_client.get("/balance/acc_1?currency=EU")
    assert response.status_code == 422
