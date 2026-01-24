from sqlalchemy import select, insert, update
from sqlalchemy.sql.functions import sum as sum_, coalesce
from payments_ledger.data_models.db_models import Account, LedgerEntry
from payments_ledger.services.ports import AccountSnapshot
from payments_ledger.ledger_domain.ledger_engine import EntryType


class SqlAlchemyLedgerRepo:
    def __init__(self, session, ttl_hours: int = 48) -> None:
        self.session = session
        self.ttl_hours = ttl_hours

    async def lock_account(self, account_id: str) -> AccountSnapshot | None:
        result = await self.session.execute(
            select(Account).where(Account.account_id == account_id).with_for_update()
        )

        row = result.scalar_one_or_none()
        if row is None:
            return None
        return AccountSnapshot(
            account_id=account_id,
            client_id=str(row.client_id),
            ledger_version=row.ledger_version,
            balance_type=row.balance_type.value,
            credit_limit=row.credit_limit,
        )

    async def get_balance(self, account_id: str, currency: str) -> int:
        result = await self.session.execute(
            select(coalesce(sum_(LedgerEntry.amount), 0)).where(
                LedgerEntry.account_id == account_id, LedgerEntry.currency == currency
            )
        )
        balance = result.scalar_one()
        return int(balance)

    async def insert_entry(
        self,
        account_id: str,
        ledger_version: int,
        amount: int,
        currency: str,
        entry_type: EntryType,
        request_id: str,
    ) -> None:
        stmt = insert(LedgerEntry).values(
            account_id=account_id,
            ledger_version=ledger_version,
            amount=amount,
            currency=currency,
            entry_type=entry_type,
            request_id=request_id,
        )
        await self.session.execute(stmt)

        return None

    async def update_account_version(self, account_id: str, ledger_version: int) -> None:
        await self.session.execute(
            update(Account)
            .where(Account.account_id == account_id)
            .values(ledger_version=ledger_version)
        )

        return None
