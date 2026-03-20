import pytest

from payments_ledger.adapters.cache.shared_layer import build_balance_cache_key
from payments_ledger.adapters.cache.slru_cache import SLRUBalanceCacheL1


@pytest.mark.asyncio
async def test_put_new_item_stores_it_and_exact_get_returns_value(balance_cache_item_factory):
    cache = SLRUBalanceCacheL1(capacity=4, protected_ratio=0.5)
    item = balance_cache_item_factory(balance=250, ledger_version=3)

    await cache.put(item)

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=3,
    )

    assert result is not None
    assert result.balance == 250
    assert result.ledger_version == 3


@pytest.mark.asyncio
async def test_exact_hit_in_probation_promotes_item_to_protected(balance_cache_item_factory):
    cache = SLRUBalanceCacheL1(capacity=4, protected_ratio=0.5)
    item = balance_cache_item_factory(ledger_version=1)

    await cache.put(item)

    key = build_balance_cache_key(account_id="acc_1", currency="EUR")
    assert cache._nodes[key].segment == "probation"

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=1,
    )

    assert result is not None
    assert cache._nodes[key].segment == "protected"
    assert len(cache._protected_cache) == 1
    assert len(cache._probation_cache) == 0


@pytest.mark.asyncio
async def test_stale_older_cached_version_returns_miss_and_removes_entry(
    balance_cache_item_factory,
):
    cache = SLRUBalanceCacheL1(capacity=4, protected_ratio=0.5)

    await cache.put(balance_cache_item_factory(ledger_version=2))

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=3,
    )

    key = build_balance_cache_key(account_id="acc_1", currency="EUR")

    assert result is None
    assert key not in cache._nodes
    assert len(cache._protected_cache) == 0
    assert len(cache._probation_cache) == 0


@pytest.mark.asyncio
async def test_newer_cached_version_returns_miss_without_removal(balance_cache_item_factory):
    cache = SLRUBalanceCacheL1(capacity=4, protected_ratio=0.5)

    await cache.put(balance_cache_item_factory(balance=500, ledger_version=5))

    miss = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=4,
    )

    exact = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=5,
    )

    key = build_balance_cache_key(account_id="acc_1", currency="EUR")

    assert miss is None
    assert key in cache._nodes
    assert exact is not None
    assert exact.balance == 500
    assert exact.ledger_version == 5


@pytest.mark.asyncio
async def test_put_older_version_does_not_overwrite_newer(balance_cache_item_factory):
    cache = SLRUBalanceCacheL1(capacity=4, protected_ratio=0.5)

    await cache.put(balance_cache_item_factory(balance=500, ledger_version=5))
    await cache.put(balance_cache_item_factory(balance=400, ledger_version=4))

    result = await cache.get_if_fresh(
        account_id="acc_1",
        currency="EUR",
        expected_version=5,
    )

    assert result is not None
    assert result.balance == 500
    assert result.ledger_version == 5
