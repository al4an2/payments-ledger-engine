from time import time

from payments_ledger.services.ports import BalanceCachedData, BalanceCacheWriteData


def build_balance_cache_key(account_id: str, currency: str) -> str:
    return f"balance:{account_id}:{currency}"


def to_cached_data(item: BalanceCacheWriteData) -> BalanceCachedData:
    now_ts_ms = int(time() * 1000)
    return BalanceCachedData(
        account_id=item.account_id,
        currency=item.currency,
        balance=item.balance,
        ledger_version=item.ledger_version,
        updated_at_ts_ms=now_ts_ms,
    )
