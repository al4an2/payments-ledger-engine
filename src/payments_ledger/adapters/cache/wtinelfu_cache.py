from __future__ import annotations

# import asyncio

from payments_ledger.services.ports import BalanceCachedData, BalanceCacheWriteData
# from payments_ledger.adapters.cache.structures import _Node, _RecencyList
# from payments_ledger.adapters.cache.shared_layer import build_balance_cache_key

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
        self,
        capacity: int,
    ) -> None:
        pass

    async def get_if_fresh(
        self, account_id: str, currency: str, expected_version: int
    ) -> BalanceCachedData | None:
        pass

    async def put(self, item: BalanceCacheWriteData) -> None:
        pass

    async def invalidate(self, account_id: str, currency: str) -> None:
        pass
