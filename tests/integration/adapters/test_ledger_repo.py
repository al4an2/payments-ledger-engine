import pytest
from sqlalchemy import select

from payments_ledger.adapters.db.ledger_repo import SqlAlchemyLedgerRepo
from payments_ledger.data_models.db_models import Account
from payments_ledger.ledger_domain.ledger_engine import BalanceType, EntryType


@pytest.mark.asyncio
async def test_get_account_for_client_returns_snapshot(db_session, seed_client_account):
    await seed_client_account(db_session)

    repo = SqlAlchemyLedgerRepo(db_session)
    async with db_session.begin():
        snap = await repo.get_account_for_client("acc_1", "client_1")

    assert snap is not None
    assert snap.account_id == "acc_1"
    assert snap.client_id == "client_1"
    assert snap.ledger_version == 0
    assert snap.balance_type == BalanceType.DEBIT_ONLY


@pytest.mark.asyncio
async def test_get_account_for_client_returns_none(db_session, seed_client_account):
    await seed_client_account(db_session)

    repo = SqlAlchemyLedgerRepo(db_session)
    async with db_session.begin():
        snap = await repo.get_account_for_client("acc_1", "other_client")
    assert snap is None


@pytest.mark.asyncio
async def test_lock_account_for_client_returns_snapshot(db_session, seed_client_account):
    await seed_client_account(db_session)

    repo = SqlAlchemyLedgerRepo(db_session)
    async with db_session.begin():
        snap = await repo.lock_account_for_client("acc_1", "client_1")

    assert snap is not None
    assert snap.account_id == "acc_1"
    assert snap.client_id == "client_1"
    assert snap.ledger_version == 0
    assert snap.balance_type == BalanceType.DEBIT_ONLY


@pytest.mark.asyncio
async def test_lock_account_for_client_returns_none(db_session):
    repo = SqlAlchemyLedgerRepo(db_session)
    async with db_session.begin():
        snap = await repo.lock_account_for_client("missing", "client_1")
    assert snap is None


@pytest.mark.asyncio
async def test_get_balance_no_entries_returns_zero(db_session, seed_client_account):
    await seed_client_account(db_session)

    repo = SqlAlchemyLedgerRepo(db_session)
    async with db_session.begin():
        balance = await repo.get_balance("acc_1", "EUR")

    assert balance == 0


@pytest.mark.asyncio
async def test_insert_entry_and_get_balance(db_session, seed_client_account):
    await seed_client_account(db_session)

    repo = SqlAlchemyLedgerRepo(db_session)
    async with db_session.begin():
        await repo.insert_entry(
            account_id="acc_1",
            ledger_version=1,
            amount=-150,
            currency="EUR",
            entry_type=EntryType.DEBIT,
            request_id="r1",
        )
        await repo.insert_entry(
            account_id="acc_1",
            ledger_version=2,
            amount=50,
            currency="EUR",
            entry_type=EntryType.CREDIT,
            request_id="r2",
        )
        balance = await repo.get_balance("acc_1", "EUR")

    assert balance == -100


@pytest.mark.asyncio
async def test_update_account_version(db_session, seed_client_account):
    await seed_client_account(db_session, ledger_version=0)

    repo = SqlAlchemyLedgerRepo(db_session)
    async with db_session.begin():
        await repo.update_account_version("acc_1", 5)
        result = await db_session.execute(select(Account).where(Account.account_id == "acc_1"))
        account = result.scalar_one()

    assert account.ledger_version == 5
