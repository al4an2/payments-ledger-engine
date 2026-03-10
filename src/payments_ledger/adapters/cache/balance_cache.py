from payments_ledger.services.ports import BalanceCachedData
from payments_ledger.adapters.cache.shared_layer import build_balance_cache_key


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

    async def put(self, item: BalanceCachedData) -> None:
        pass

    async def invalidate(self, account_id: str, currency: str) -> None:
        pass


class VersionedMapCache:
    def __init__(self) -> None:
        self._cache: dict[str, BalanceCachedData] = {}

    async def get_if_fresh(
        self, account_id: str, currency: str, expected_version: int
    ) -> BalanceCachedData | None:
        key = build_balance_cache_key(account_id=account_id, currency=currency)
        cached = self._cache.get(key)

        if not cached:
            return None

        if cached.ledger_version < expected_version:
            await self.invalidate(account_id, currency)
            return None

        if cached.ledger_version > expected_version:
            return None

        return cached

    async def put(self, item: BalanceCachedData) -> None:
        key = build_balance_cache_key(account_id=item.account_id, currency=item.currency)
        cached = self._cache.get(key)

        if cached is None or item.ledger_version >= cached.ledger_version:
            self._cache[key] = item

    async def invalidate(self, account_id: str, currency: str) -> None:
        key = build_balance_cache_key(account_id=account_id, currency=currency)
        self._cache.pop(key, None)
