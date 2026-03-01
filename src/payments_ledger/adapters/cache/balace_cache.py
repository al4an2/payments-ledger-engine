from payments_ledger.services.ports import BalanceCachedData


class WTinyLFUBalanceCacheL1:
    def __init__(
        self,
        capacity: int,
    ) -> None:
        pass

    async def get_if_fresh(self, key: str, expected_version: int) -> BalanceCachedData | None:
        pass

    async def put(self, item: BalanceCachedData) -> None:
        pass

    async def invalidate(self, key: str) -> None:
        pass
