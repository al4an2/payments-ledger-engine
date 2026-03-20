import pytest
from payments_ledger.services.ports import BalanceCacheWriteData


@pytest.fixture
def balance_cache_item_factory():
    def _make(
        *,
        account_id: str = "acc_1",
        currency: str = "EUR",
        balance: int = 100,
        ledger_version: int,
    ) -> BalanceCacheWriteData:
        return BalanceCacheWriteData(
            account_id=account_id,
            currency=currency,
            balance=balance,
            ledger_version=ledger_version,
        )

    return _make
