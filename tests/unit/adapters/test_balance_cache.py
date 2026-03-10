import pytest

from payments_ledger.adapters.cache.balance_cache import VersionedMapCache
from payments_ledger.services.ports import BalanceCachedData


def _item(
    *,
    account_id: str = "acc_1",
    currency: str = "EUR",
    balance: int = 100,
    ledger_version: int,
    updated_at_ts_ms: int = 1_700_000_000_000,
) -> BalanceCachedData:
    return BalanceCachedData(
        account_id=account_id,
        currency=currency,
        balance=balance,
        ledger_version=ledger_version,
        updated_at_ts_ms=updated_at_ts_ms,
    )


@pytest.mark.asyncio
async def test_get_if_fresh_returns_none_for_missing_key():
    cache = VersionedMapCache()

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=1,
    )

    assert result is None


@pytest.mark.asyncio
async def test_put_then_get_if_fresh_returns_item_for_exact_version():
    cache = VersionedMapCache()
    item = _item(ledger_version=3, balance=250)

    await cache.put(item)

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=3,
    )

    assert result == item


@pytest.mark.asyncio
async def test_get_if_fresh_returns_none_and_invalidates_when_cached_version_is_older():
    cache = VersionedMapCache()
    item = _item(ledger_version=2)

    await cache.put(item)

    first_try = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=3,
    )

    assert first_try is None

    second_try = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=2,
    )
    assert second_try is None


@pytest.mark.asyncio
async def test_get_if_fresh_returns_none_when_cached_version_is_newer():
    cache = VersionedMapCache()
    item = _item(ledger_version=5)

    await cache.put(item)

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=4,
    )

    assert result is None


@pytest.mark.asyncio
async def test_put_does_not_overwrite_newer_version_with_older_one():
    cache = VersionedMapCache()

    await cache.put(_item(ledger_version=5, balance=500))
    await cache.put(_item(ledger_version=4, balance=400))

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=5,
    )

    assert result is not None
    assert result.ledger_version == 5
    assert result.balance == 500


@pytest.mark.asyncio
async def test_invalidate_removes_item():
    cache = VersionedMapCache()
    item = _item(ledger_version=1)

    await cache.put(item)
    await cache.invalidate(account_id="acc_1", currency="EUR")

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=1,
    )

    assert result is None


@pytest.mark.asyncio
async def test_put_overwrites_with_newer_version():
    cache = VersionedMapCache()

    await cache.put(_item(balance=100, ledger_version=3))
    await cache.put(_item(balance=250, ledger_version=4))

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=4,
    )

    assert result is not None
    assert result.ledger_version == 4
    assert result.balance == 250


@pytest.mark.asyncio
async def test_put_overwrites_same_version():
    cache = VersionedMapCache()

    await cache.put(_item(balance=100, ledger_version=3))
    await cache.put(_item(balance=250, ledger_version=3, updated_at_ts_ms=1_700_000_000_100))

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=3,
    )

    assert result is not None
    assert result.ledger_version == 3
    assert result.balance == 250
    assert result.updated_at_ts_ms == 1_700_000_000_100


@pytest.mark.asyncio
async def test_stale_older_entry_is_removed_after_miss():
    cache = VersionedMapCache()

    await cache.put(_item(balance=100, ledger_version=2))

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=3,
    )

    assert result is None

    second_try = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=2,
    )

    assert second_try is None


@pytest.mark.asyncio
async def test_newer_cached_entry_returns_miss_but_stays_in_cache():
    cache = VersionedMapCache()

    await cache.put(_item(balance=500, ledger_version=5))

    older_expected = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=4,
    )

    assert older_expected is None

    exact_expected = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=5,
    )

    assert exact_expected is not None
    assert exact_expected.ledger_version == 5
    assert exact_expected.balance == 500


@pytest.mark.asyncio
async def test_cache_keys_are_isolated_by_account_and_currency():
    cache = VersionedMapCache()

    await cache.put(_item(account_id="acc_1", currency="EUR", balance=100, ledger_version=1))
    await cache.put(_item(account_id="acc_1", currency="USD", balance=200, ledger_version=1))
    await cache.put(_item(account_id="acc_2", currency="EUR", balance=300, ledger_version=1))

    eur_acc1 = await cache.get_if_fresh("acc_1", "EUR", expected_version=1)
    usd_acc1 = await cache.get_if_fresh("acc_1", "USD", expected_version=1)
    eur_acc2 = await cache.get_if_fresh("acc_2", "EUR", expected_version=1)

    assert eur_acc1 is not None
    assert eur_acc1.balance == 100

    assert usd_acc1 is not None
    assert usd_acc1.balance == 200

    assert eur_acc2 is not None
    assert eur_acc2.balance == 300
