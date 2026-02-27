import pytest_asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker

from payments_ledger.api.main import app
from payments_ledger.api.deps import get_uow, get_client_id
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


@pytest_asyncio.fixture
async def raw_api_client():
    app.dependency_overrides.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def seed_client_account():
    async def _seed(
        session,
        *,
        client_id: str = "client_1",
        account_id: str = "acc_1",
        balance_type: BalanceType = BalanceType.DEBIT_ONLY,
        credit_limit: int | None = None,
        ledger_version: int = 0,
        api_key_hash: str | None = None,
    ) -> None:
        session.add(
            Client(
                client_id=client_id,
                name="Test Client",
                api_key_hash=api_key_hash or f"hash_{client_id}",
            )
        )
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

    return _seed


@pytest.fixture
def seed_ledger_entries():
    async def _seed(
        session,
        *,
        entries: list[dict] | None = None,
    ) -> None:
        rows = entries or [
            {
                "account_id": "acc_1",
                "ledger_version": 1,
                "amount": -150,
                "currency": "EUR",
                "entry_type": EntryType.DEBIT,
                "request_id": "r1",
            },
            {
                "account_id": "acc_1",
                "ledger_version": 2,
                "amount": 50,
                "currency": "EUR",
                "entry_type": EntryType.CREDIT,
                "request_id": "r2",
            },
        ]

        session.add_all(
            [
                LedgerEntry(
                    account_id=row["account_id"],
                    ledger_version=row["ledger_version"],
                    amount=row["amount"],
                    currency=row["currency"],
                    entry_type=row["entry_type"],
                    request_id=row["request_id"],
                )
                for row in rows
            ]
        )
        await session.commit()

    return _seed
