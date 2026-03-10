from payments_ledger.services.ports import BalanceCachedData, BalanceCacheWriteData
from payments_ledger.adapters.cache.shared_layer import build_balance_cache_key
from time import time


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

    async def put(self, item: BalanceCacheWriteData) -> None:
        key = build_balance_cache_key(account_id=item.account_id, currency=item.currency)
        cached = self._cache.get(key)

        if cached is None or item.ledger_version >= cached.ledger_version:
            now_ts_ms = int(time() * 1000)

            cached_item = BalanceCachedData(
                account_id=item.account_id,
                currency=item.currency,
                balance=item.balance,
                ledger_version=item.ledger_version,
                updated_at_ts_ms=now_ts_ms,
            )
            self._cache[key] = cached_item

    async def invalidate(self, account_id: str, currency: str) -> None:
        key = build_balance_cache_key(account_id=account_id, currency=currency)
        self._cache.pop(key, None)
