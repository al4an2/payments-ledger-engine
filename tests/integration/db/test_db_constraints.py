import pytest
from sqlalchemy.exc import IntegrityError

from payments_ledger.data_models.db_models import Account, LedgerEntry
from payments_ledger.ledger_domain.ledger_engine import BalanceType, EntryType


@pytest.mark.asyncio
async def test_account_debit_only_rejects_credit_limit(db_session, seed_client):
    await seed_client(db_session)

    db_session.add(
        Account(
            account_id="acc_invalid_debit_only",
            client_id="client_1",
            balance_type=BalanceType.DEBIT_ONLY,
            credit_limit=1000,
            ledger_version=0,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_account_rejects_negative_credit_limit(db_session, seed_client):
    await seed_client(db_session)

    db_session.add(
        Account(
            account_id="acc_invalid_credit_limit",
            client_id="client_1",
            balance_type=BalanceType.CREDIT_ALLOWED,
            credit_limit=-1,
            ledger_version=0,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entry_type", "amount"),
    [
        (EntryType.DEBIT, 100),
        (EntryType.CREDIT, -100),
    ],
)
async def test_ledger_entry_rejects_invalid_amount_sign(
    db_session,
    seed_client_account,
    entry_type: EntryType,
    amount: int,
):
    await seed_client_account(
        db_session,
        account_id="acc_constraints",
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=1000,
    )

    db_session.add(
        LedgerEntry(
            account_id="acc_constraints",
            ledger_version=1 if entry_type == EntryType.DEBIT else 2,
            amount=amount,
            currency="EUR",
            entry_type=entry_type,
            request_id=f"req-{entry_type.value.lower()}-invalid-sign",
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()
