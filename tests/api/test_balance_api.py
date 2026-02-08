import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker

from payments_ledger.api.main import app, get_uow
from payments_ledger.api.auth import get_client_id
from payments_ledger.adapters.db.uow import SqlAlchemyUnitOfWork
from payments_ledger.data_models.db_models import Client, Account, LedgerEntry
from payments_ledger.ledger_domain.ledger_engine import BalanceType, EntryType


@pytest_asyncio.fixture
async def api_client(async_engine):
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

    def override_get_uow():
        return SqlAlchemyUnitOfWork(session_factory)

    async def override_get_client_id():
        return "client_1"

    app.dependency_overrides[get_uow] = override_get_uow
    app.dependency_overrides[get_client_id] = override_get_client_id
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _seed_client_account(session):
    session.add(Client(client_id="client_1", name="Test Client", api_key_hash="hash_1"))
    session.add(
        Account(
            account_id="acc_1",
            client_id="client_1",
            balance_type=BalanceType.DEBIT_ONLY,
            credit_limit=None,
            ledger_version=0,
        )
    )
    await session.commit()


async def _seed_ledger_entries(session):
    session.add_all(
        [
            LedgerEntry(
                account_id="acc_1",
                ledger_version=1,
                amount=-150,
                currency="EUR",
                entry_type=EntryType.DEBIT,
                request_id="r1",
            ),
            LedgerEntry(
                account_id="acc_1",
                ledger_version=2,
                amount=50,
                currency="EUR",
                entry_type=EntryType.CREDIT,
                request_id="r2",
            ),
        ]
    )
    await session.commit()


@pytest.mark.asyncio
async def test_balance_ok(api_client, db_session):
    await _seed_client_account(db_session)
    await _seed_ledger_entries(db_session)

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
