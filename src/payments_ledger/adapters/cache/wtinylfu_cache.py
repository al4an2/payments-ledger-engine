from __future__ import annotations

import asyncio

from payments_ledger.services.ports import BalanceCachedData, BalanceCacheWriteData
from payments_ledger.adapters.cache.structures import _Node, _RecencyList
from payments_ledger.adapters.cache.shared_layer import build_balance_cache_key, to_cached_data

_BASE_SEEDS: tuple[int, ...] = (
    0xC3A5C85C97CB3127,
    0xB492B66FBE98F273,
    0x9AE16A3B2F90404F,
    0xCBF29CE484222325,
)

_MAX_COUNTER = 15


class _FrequencySketch:
    def __init__(
        self,
        width: int = 256,
        reset_after: int = 10_000,
        seeds: tuple[int, ...] = _BASE_SEEDS,
        max_counter: int = _MAX_COUNTER,
    ) -> None:
        if width < 16:
            raise ValueError("Width must be 16 or more")
        if width & (width - 1) != 0:
            raise ValueError("width must be a power of two")
        if reset_after < 1:
            raise ValueError("reset_after must be positive")
        if len(seeds) < 1:
            raise ValueError("seeds must be positive")
        if max_counter < 1:
            raise ValueError("max_counter must be positive")

        self._width: int = width
        self._mask = width - 1
        self._depth: int = len(seeds)
        self._seeds: tuple[int, ...] = seeds
        self._operations: int = 0
        self._max_counter: int = max_counter
        self._reset_after: int = reset_after
        self._table: list[list[int]] = [[0] * self._width for _ in range(self._depth)]

    def _index(self, key: str, seed: int) -> int:
        return hash((seed, key)) & self._mask

    def _maybe_reset(self) -> None:
        if self._operations >= self._reset_after:
            self._reset()

    def _reset(self) -> None:
        for row in range(self._depth):
            for col in range(self._width):
                self._table[row][col] //= 2
        self._operations = 0

    def increment(self, key: str) -> None:
        for row, seed in enumerate(self._seeds):
            idx = self._index(key=key, seed=seed)
            counter = self._table[row][idx]
            self._table[row][idx] = min(counter + 1, self._max_counter)
        self._operations += 1
        self._maybe_reset()

    def estimate(self, key: str) -> int:
        estimates = []
        for row, seed in enumerate(self._seeds):
            idx = self._index(key=key, seed=seed)
            estimates.append(self._table[row][idx])
        return min(estimates)


class WTinyLFUBalanceCacheL1:
    def __init__(
        self, capacity: int, protected_ratio: float = 0.8, window_ratio: float = 0.05
    ) -> None:
        if capacity < 3:
            raise ValueError("Minimal capacity size = 3")
        if not 0 < protected_ratio < 1:
            raise ValueError("Protected ratio must be between 0 and 1")
        if not 0 < window_ratio < 1:
            raise ValueError("Window ratio must be between 0 and 1, recommend 0.01-0.05")

        _MIN_WINDOW = 1
        self._capacity: int = capacity
        self._window_capacity: int = max(_MIN_WINDOW, int(capacity * window_ratio))
        main_capacity = capacity - self._window_capacity

        self._protected_capacity: int = int(main_capacity * protected_ratio)
        self._probation_capacity: int = main_capacity - self._protected_capacity
        self._nodes: dict[str, _Node] = {}
        self._protected_cache = _RecencyList()
        self._probation_cache = _RecencyList()
        self._window_cache = _RecencyList()
        self._admission = _FrequencySketch()
        self._lock = asyncio.Lock()

        if self._protected_capacity < 1:
            raise ValueError("Minimal protected_capacity size = 1")
        if self._probation_capacity < 1:
            raise ValueError("Minimal probation_capacity size = 1")

    def _remove_node(self, node: _Node) -> None:
        goal_node = self._nodes.get(node.key)

        if goal_node is not node:
            raise RuntimeError("node is out of sync with cache segments")

        if node.segment == "probation":
            self._probation_cache.remove(node)
        elif node.segment == "protected":
            self._protected_cache.remove(node)
        elif node.segment == "window":
            self._window_cache.remove(node)
        else:
            raise RuntimeError("Unexpected segment in node")

        del self._nodes[node.key]

    def _touch(self, node: _Node) -> None:
        if node.segment == "probation":
            self._promote_to_protected(node)
        elif node.segment == "protected":
            self._protected_cache.move_to_front(node)
        elif node.segment == "window":
            self._touch_window(node)
        else:
            raise RuntimeError("Unexpected segment in node")

        self._admission.increment(node.key)

    def _evict_probation_tail_if_needed(self) -> None:
        if len(self._probation_cache) > self._probation_capacity:
            tail_node = self._probation_cache.pop_tail()

            if tail_node is None:
                raise RuntimeError("probation overflow without eviction candidate")

            if tail_node.key not in self._nodes:
                raise RuntimeError("evicted probation node is missing from index")

            del self._nodes[tail_node.key]

    def _demote_to_probation_if_needed(self) -> None:
        if len(self._protected_cache) > self._protected_capacity:
            tail_node = self._protected_cache.pop_tail()

            if tail_node is None:
                raise RuntimeError("protected overflow had no tail")

            tail_node.segment = "probation"
            self._probation_cache.append_front(tail_node)
            self._evict_probation_tail_if_needed()

    def _promote_to_protected(self, node: _Node) -> None:
        self._probation_cache.remove(node)

        node.segment = "protected"
        self._protected_cache.append_front(node)
        self._demote_to_probation_if_needed()

    def _insert_new_into_window(self, node: _Node) -> None:
        self._nodes[node.key] = node
        self._window_cache.append_front(node)
        self._admission.increment(node.key)

        if len(self._window_cache) > self._window_capacity:
            candidate = self._window_cache.pop_tail()
            if not candidate:
                raise RuntimeError("Window_cache is full and haven't tail at the same time")
            self._admit_window_candidate(candidate)

    def _touch_window(self, candidate: _Node) -> None:
        self._window_cache.move_to_front(candidate)

    def _peek_probation_victim(self) -> _Node | None:
        if len(self._probation_cache) > 0:
            return self._probation_cache.peek_tail()
        return None

    def _admit_window_candidate(self, candidate: _Node) -> None:
        if len(self._probation_cache) < self._probation_capacity:
            self._insert_into_probation(candidate)
            return

        victim = self._peek_probation_victim()
        if not victim:
            raise RuntimeError("Probation_cache is full and haven't tail at the same time")

        candidate_freq = self._admission.estimate(candidate.key)
        victim_freq = self._admission.estimate(victim.key)
        if victim_freq < candidate_freq:
            self._probation_cache.remove(victim)
            self._probation_cache.append_front(candidate)
            candidate.segment = "probation"

            del self._nodes[victim.key]

        else:
            del self._nodes[candidate.key]

    def _insert_into_probation(self, node: _Node) -> None:
        node.segment = "probation"
        self._probation_cache.append_front(node)

    async def get_if_fresh(
        self, account_id: str, currency: str, expected_version: int
    ) -> BalanceCachedData | None:
        async with self._lock:
            key = build_balance_cache_key(account_id=account_id, currency=currency)

            cached = self._nodes.get(key)

            if cached is None:
                return None

            cached_version = cached.value.ledger_version

            if expected_version > cached_version:
                self._remove_node(cached)
                return None

            if expected_version < cached_version:
                return None

            self._touch(node=cached)
            return cached.value

    async def put(self, item: BalanceCacheWriteData) -> None:
        async with self._lock:
            new_key = build_balance_cache_key(account_id=item.account_id, currency=item.currency)
            cached = self._nodes.get(new_key)

            if cached and item.ledger_version < cached.value.ledger_version:
                return

            data = to_cached_data(item)
            if cached is None:
                self._insert_new_into_window(_Node(key=new_key, value=data, segment="window"))

            else:
                cached.value = data
                self._touch(cached)

    async def invalidate(self, account_id: str, currency: str) -> None:
        async with self._lock:
            key = build_balance_cache_key(account_id=account_id, currency=currency)
            cached = self._nodes.get(key)
            if cached:
                self._remove_node(cached)
