def build_balance_cache_key(account_id: str, currency: str) -> str:
    return f"balance:{account_id}:{currency}"
