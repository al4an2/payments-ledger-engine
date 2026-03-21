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


@pytest.mark.asyncio
async def test_protected_demotes_tail_into_probation(balance_cache_item_factory):
    cache = SLRUBalanceCacheL1(capacity=4, protected_ratio=0.5)

    await cache.put(balance_cache_item_factory(account_id="acc_1", ledger_version=1))
    await cache.put(balance_cache_item_factory(account_id="acc_2", ledger_version=1))

    await cache.get_if_fresh("acc_1", "EUR", expected_version=1)
    await cache.get_if_fresh("acc_2", "EUR", expected_version=1)

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")
    key_2 = build_balance_cache_key(account_id="acc_2", currency="EUR")

    assert cache._nodes[key_1].segment == "protected"
    assert cache._nodes[key_2].segment == "protected"

    await cache.put(balance_cache_item_factory(account_id="acc_3", ledger_version=1))
    await cache.put(balance_cache_item_factory(account_id="acc_4", ledger_version=1))

    await cache.get_if_fresh("acc_3", "EUR", expected_version=1)

    key_3 = build_balance_cache_key(account_id="acc_3", currency="EUR")
    key_4 = build_balance_cache_key(account_id="acc_4", currency="EUR")

    assert cache._nodes[key_3].segment == "protected"
    assert cache._nodes[key_2].segment == "protected"

    assert cache._nodes[key_1].segment == "probation"
    assert cache._nodes[key_4].segment == "probation"

    assert len(cache._protected_cache) == 2
    assert len(cache._probation_cache) == 2


@pytest.mark.asyncio
async def test_exact_hit_in_protected_keeps_node_in_protected_and_refreshes_recency(
    balance_cache_item_factory,
):
    cache = SLRUBalanceCacheL1(capacity=4, protected_ratio=0.5)

    await cache.put(balance_cache_item_factory(account_id="acc_1", ledger_version=1))
    await cache.put(balance_cache_item_factory(account_id="acc_2", ledger_version=1))

    await cache.get_if_fresh("acc_1", "EUR", expected_version=1)
    await cache.get_if_fresh("acc_2", "EUR", expected_version=1)

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")
    key_2 = build_balance_cache_key(account_id="acc_2", currency="EUR")

    await cache.get_if_fresh("acc_1", "EUR", expected_version=1)

    await cache.put(balance_cache_item_factory(account_id="acc_3", ledger_version=1))
    await cache.put(balance_cache_item_factory(account_id="acc_4", ledger_version=1))
    await cache.get_if_fresh("acc_3", "EUR", expected_version=1)

    assert cache._nodes[key_1].segment == "protected"
    assert cache._nodes[key_2].segment == "probation"


@pytest.mark.asyncio
async def test_probation_overflow_evicts_tail(balance_cache_item_factory):
    cache = SLRUBalanceCacheL1(capacity=4, protected_ratio=0.5)

    await cache.put(balance_cache_item_factory(account_id="acc_1", ledger_version=1))
    await cache.put(balance_cache_item_factory(account_id="acc_2", ledger_version=1))
    await cache.put(balance_cache_item_factory(account_id="acc_3", ledger_version=1))

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")
    key_2 = build_balance_cache_key(account_id="acc_2", currency="EUR")
    key_3 = build_balance_cache_key(account_id="acc_3", currency="EUR")

    assert key_1 not in cache._nodes
    assert cache._nodes[key_2].segment == "probation"
    assert cache._nodes[key_3].segment == "probation"
    assert len(cache._probation_cache) == 2


@pytest.mark.asyncio
async def test_put_newer_version_updates_value_and_counts_as_access(
    balance_cache_item_factory,
):
    cache = SLRUBalanceCacheL1(capacity=4, protected_ratio=0.5)

    await cache.put(
        balance_cache_item_factory(
            account_id="acc_1",
            balance=100,
            ledger_version=1,
        )
    )

    key = build_balance_cache_key(account_id="acc_1", currency="EUR")
    assert cache._nodes[key].segment == "probation"

    await cache.put(
        balance_cache_item_factory(
            account_id="acc_1",
            balance=250,
            ledger_version=2,
        )
    )

    node = cache._nodes[key]

    assert node.value.balance == 250
    assert node.value.ledger_version == 2
    assert node.segment == "protected"
