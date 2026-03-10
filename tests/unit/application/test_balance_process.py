import pytest

from payments_ledger.ledger_domain.ledger_engine import BalanceType
from payments_ledger.services.payments import balance_process
from payments_ledger.services.ports import (
    AccountSnapshot,
    BalanceCachedData,
    GetBalanceCommand,
)


class FakeLedgerRepo:
    def __init__(self) -> None:
        self.get_balance_called = 0

    async def get_account_for_client(
        self, account_id: str, client_id: str
    ) -> AccountSnapshot | None:
        return AccountSnapshot(
            account_id=account_id,
            client_id=client_id,
            ledger_version=3,
            balance_type=BalanceType.DEBIT_ONLY,
            credit_limit=None,
        )

    async def get_balance(self, _account_id: str, _currency: str) -> int:
        self.get_balance_called += 1
        return -999


class FakeUoW:
    def __init__(self) -> None:
        self.ledger_repo = FakeLedgerRepo()

    async def __aenter__(self) -> "FakeUoW":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakeBalanceCacheL1:
    def __init__(self) -> None:
        self.put_called = 0

    async def get_if_fresh(
        self, account_id: str, currency: str, _expected_version: int
    ) -> BalanceCachedData | None:
        return BalanceCachedData(
            account_id=account_id,
            currency=currency,
            balance=250,
            ledger_version=3,
            updated_at_ts_ms=1_700_000_000_000,
        )

    async def put(self, _item) -> None:
        self.put_called += 1

    async def invalidate(self, _account_id: str, _currency: str) -> None:
        return None


@pytest.mark.asyncio
async def test_balance_process_returns_cached_balance_on_fresh_hit():
    uow = FakeUoW()
    cache = FakeBalanceCacheL1()
    payload = GetBalanceCommand(
        account_id="acc_1",
        currency="EUR",
        request_id="req-bal-cache-hit-1",
    )

    result = await balance_process(
        uow=uow,
        client_id="client_1",
        payload=payload,
        request_id="req-bal-cache-hit-1",
        balance_cache_l1=cache,
    )

    assert result == {
        "account_id": "acc_1",
        "currency": "EUR",
        "balance": 250,
        "status": "OK",
        "request_id": "req-bal-cache-hit-1",
        "error_code": None,
        "error_message": None,
    }
    assert uow.ledger_repo.get_balance_called == 0
    assert cache.put_called == 0
