import pytest

from payments_ledger.data_models.db_models import Account, Client
from payments_ledger.ledger_domain.ledger_engine import BalanceType


@pytest.fixture
def seed_client():
    async def _seed(
        session,
        *,
        client_id: str = "client_1",
        name: str = "Test Client",
        api_key_hash: str = "hash_1",
    ) -> None:
        session.add(Client(client_id=client_id, name=name, api_key_hash=api_key_hash))
        await session.commit()

    return _seed


@pytest.fixture
def seed_account():
    async def _seed(
        session,
        *,
        client_id: str = "client_1",
        account_id: str = "acc_1",
        balance_type: BalanceType = BalanceType.DEBIT_ONLY,
        credit_limit: int | None = None,
        ledger_version: int = 0,
    ) -> None:
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
def seed_client_account(seed_client, seed_account):
    async def _seed(
        session,
        *,
        client_id: str = "client_1",
        account_id: str = "acc_1",
        name: str = "Test Client",
        api_key_hash: str = "hash_1",
        balance_type: BalanceType = BalanceType.DEBIT_ONLY,
        credit_limit: int | None = None,
        ledger_version: int = 0,
    ) -> None:
        await seed_client(
            session,
            client_id=client_id,
            name=name,
            api_key_hash=api_key_hash,
        )
        await seed_account(
            session,
            client_id=client_id,
            account_id=account_id,
            balance_type=balance_type,
            credit_limit=credit_limit,
            ledger_version=ledger_version,
        )

    return _seed
