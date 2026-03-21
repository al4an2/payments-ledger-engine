import pytest

from payments_ledger.adapters.cache.shared_layer import build_balance_cache_key
from payments_ledger.adapters.cache.wtinylfu_cache import WTinyLFUBalanceCacheL1


@pytest.mark.asyncio
async def test_put_new_item_inserts_entry_into_window(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=4, protected_ratio=0.5)
    item = balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)

    await cache.put(item)

    key = build_balance_cache_key(account_id="acc_1", currency="EUR")
    assert cache._nodes[key].segment == "window"


@pytest.mark.asyncio
async def test_window_hit_keeps_entry_in_window_and_refreshes_recency(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=10, protected_ratio=0.4, window_ratio=0.2)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_2", currency="EUR", ledger_version=1)
    )

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")
    key_2 = build_balance_cache_key(account_id="acc_2", currency="EUR")

    assert cache._nodes[key_1].segment == "window"
    assert cache._nodes[key_2].segment == "window"
    assert cache._window_cache._head is cache._nodes[key_2]

    await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=1)

    assert cache._nodes[key_1].segment == "window"
    assert cache._window_cache._head is cache._nodes[key_1]
    assert cache._window_cache._tail is cache._nodes[key_2]


@pytest.mark.asyncio
async def test_window_overflow_moves_tail_candidate_into_probation_when_probation_has_space(
    balance_cache_item_factory,
):
    cache = WTinyLFUBalanceCacheL1(capacity=4, protected_ratio=0.5, window_ratio=0.25)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_2", currency="EUR", ledger_version=1)
    )

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")
    key_2 = build_balance_cache_key(account_id="acc_2", currency="EUR")

    assert cache._nodes[key_1].segment == "probation"
    assert cache._nodes[key_2].segment == "window"
    assert len(cache._probation_cache) == 1
    assert len(cache._window_cache) == 1


@pytest.mark.asyncio
async def test_exact_hit_in_probation_promotes_entry_to_protected(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=4, protected_ratio=0.5, window_ratio=0.25)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_2", currency="EUR", ledger_version=1)
    )

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")

    assert cache._nodes[key_1].segment == "probation"

    result = await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=1)

    assert result is not None
    assert cache._nodes[key_1].segment == "protected"
    assert len(cache._protected_cache) == 1
    assert len(cache._probation_cache) == 0


@pytest.mark.asyncio
async def test_exact_hit_in_protected_refreshes_recency_and_keeps_entry_protected(
    balance_cache_item_factory,
):
    cache = WTinyLFUBalanceCacheL1(capacity=5, protected_ratio=0.5, window_ratio=0.2)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_2", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_3", currency="EUR", ledger_version=1)
    )

    await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=1)
    await cache.get_if_fresh(account_id="acc_2", currency="EUR", expected_version=1)
    await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=1)

    await cache.put(
        balance_cache_item_factory(account_id="acc_4", currency="EUR", ledger_version=1)
    )
    await cache.get_if_fresh(account_id="acc_3", currency="EUR", expected_version=1)

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")
    key_2 = build_balance_cache_key(account_id="acc_2", currency="EUR")
    key_3 = build_balance_cache_key(account_id="acc_3", currency="EUR")

    assert cache._nodes[key_1].segment == "protected"
    assert cache._nodes[key_3].segment == "protected"
    assert cache._nodes[key_2].segment == "probation"


@pytest.mark.asyncio
async def test_higher_frequency_candidate_replaces_probation_victim(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=4, protected_ratio=0.5, window_ratio=0.25)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_2", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_3", currency="EUR", ledger_version=1)
    )

    await cache.get_if_fresh(account_id="acc_3", currency="EUR", expected_version=1)
    await cache.get_if_fresh(account_id="acc_3", currency="EUR", expected_version=1)

    await cache.put(
        balance_cache_item_factory(account_id="acc_4", currency="EUR", ledger_version=1)
    )

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")
    key_2 = build_balance_cache_key(account_id="acc_2", currency="EUR")
    key_3 = build_balance_cache_key(account_id="acc_3", currency="EUR")
    key_4 = build_balance_cache_key(account_id="acc_4", currency="EUR")

    assert key_1 not in cache._nodes
    assert cache._nodes[key_2].segment == "probation"
    assert cache._nodes[key_3].segment == "probation"
    assert cache._nodes[key_4].segment == "window"


@pytest.mark.asyncio
async def test_equal_or_lower_frequency_candidate_is_rejected(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=4, protected_ratio=0.5, window_ratio=0.25)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_2", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_3", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_4", currency="EUR", ledger_version=1)
    )

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")
    key_2 = build_balance_cache_key(account_id="acc_2", currency="EUR")
    key_3 = build_balance_cache_key(account_id="acc_3", currency="EUR")
    key_4 = build_balance_cache_key(account_id="acc_4", currency="EUR")

    assert cache._nodes[key_1].segment == "probation"
    assert cache._nodes[key_2].segment == "probation"
    assert key_3 not in cache._nodes
    assert cache._nodes[key_4].segment == "window"


@pytest.mark.asyncio
async def test_stale_older_cached_version_removes_entry_from_window(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=10, protected_ratio=0.4, window_ratio=0.2)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )

    result = await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=2)

    key = build_balance_cache_key(account_id="acc_1", currency="EUR")

    assert result is None
    assert key not in cache._nodes
    assert len(cache._window_cache) == 0


@pytest.mark.asyncio
async def test_stale_older_cached_version_removes_entry_from_probation(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=4, protected_ratio=0.5, window_ratio=0.25)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_2", currency="EUR", ledger_version=1)
    )

    result = await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=2)

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")

    assert result is None
    assert key_1 not in cache._nodes
    assert len(cache._probation_cache) == 0


@pytest.mark.asyncio
async def test_stale_older_cached_version_removes_entry_from_protected(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=4, protected_ratio=0.5, window_ratio=0.25)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_2", currency="EUR", ledger_version=1)
    )
    await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=1)

    result = await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=2)

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")

    assert result is None
    assert key_1 not in cache._nodes
    assert len(cache._protected_cache) == 0


@pytest.mark.asyncio
async def test_newer_cached_version_returns_miss_without_removal(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=10, protected_ratio=0.4, window_ratio=0.2)

    await cache.put(
        balance_cache_item_factory(
            account_id="acc_1",
            currency="EUR",
            balance=500,
            ledger_version=5,
        )
    )

    miss = await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=4)
    exact = await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=5)

    key = build_balance_cache_key(account_id="acc_1", currency="EUR")

    assert miss is None
    assert key in cache._nodes
    assert exact is not None
    assert exact.balance == 500
    assert exact.ledger_version == 5


@pytest.mark.asyncio
async def test_put_older_version_does_not_overwrite_newer(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=10, protected_ratio=0.4, window_ratio=0.2)

    await cache.put(
        balance_cache_item_factory(
            account_id="acc_1",
            currency="EUR",
            balance=500,
            ledger_version=5,
        )
    )
    await cache.put(
        balance_cache_item_factory(
            account_id="acc_1",
            currency="EUR",
            balance=400,
            ledger_version=4,
        )
    )

    result = await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=5)

    assert result is not None
    assert result.balance == 500
    assert result.ledger_version == 5


@pytest.mark.asyncio
async def test_invalidate_removes_entry_from_window(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=10, protected_ratio=0.4, window_ratio=0.2)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )

    key = build_balance_cache_key(account_id="acc_1", currency="EUR")
    await cache.invalidate(account_id="acc_1", currency="EUR")

    assert key not in cache._nodes
    assert len(cache._window_cache) == 0


@pytest.mark.asyncio
async def test_invalidate_removes_entry_from_probation(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=4, protected_ratio=0.5, window_ratio=0.25)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_2", currency="EUR", ledger_version=1)
    )

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")
    await cache.invalidate(account_id="acc_1", currency="EUR")

    assert key_1 not in cache._nodes
    assert len(cache._probation_cache) == 0


@pytest.mark.asyncio
async def test_invalidate_removes_entry_from_protected(balance_cache_item_factory):
    cache = WTinyLFUBalanceCacheL1(capacity=4, protected_ratio=0.5, window_ratio=0.25)

    await cache.put(
        balance_cache_item_factory(account_id="acc_1", currency="EUR", ledger_version=1)
    )
    await cache.put(
        balance_cache_item_factory(account_id="acc_2", currency="EUR", ledger_version=1)
    )
    await cache.get_if_fresh(account_id="acc_1", currency="EUR", expected_version=1)

    key_1 = build_balance_cache_key(account_id="acc_1", currency="EUR")
    await cache.invalidate(account_id="acc_1", currency="EUR")

    assert key_1 not in cache._nodes
    assert len(cache._protected_cache) == 0
