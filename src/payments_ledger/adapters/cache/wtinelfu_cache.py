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


class _FrequencySketch:
    def __init__(
        self, width: int = 256, reset_after: int = 2048, seeds: tuple[int, ...] = _BASE_SEEDS
    ) -> None:
        if width < 16:
            raise ValueError("Width should be 16 or more")
        if reset_after < 1:
            raise ValueError("reset_after must be positive")

        self._width: int = width
        self._depth: int = len(seeds)
        self._seeds: tuple[int, ...] = seeds
        self._operations: int = 0
        self._reset_after: int = reset_after
        self._table: list[list[int]] = [[0] * self._width for _ in range(self._depth)]

    def _index(self, key, seed) -> int:
        return hash((seed, key)) % self._width

    def _maybe_reset(self):
        pass

    def _reset(self) -> None:
        pass

    def increment(self, key: str) -> None:
        for row, seed in enumerate(self._seeds):
            idx = self._index(key=key, seed=seed)
            self._table[row][idx] += 1
        self._operations += 1
        self._maybe_reset()

    def estimate(self, key: str):
        pass


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
