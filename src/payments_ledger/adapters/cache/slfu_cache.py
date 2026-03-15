from payments_ledger.services.ports import BalanceCachedData, BalanceCacheWriteData
# from payments_ledger.adapters.cache.shared_layer import build_balance_cache_key


class LFUBalanceCacheL1:
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
