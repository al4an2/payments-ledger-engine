# Versioned Balance Cache

## Status
Implemented now:
- L1 v1: in-process `VersionedMapCache` wired into `GET /balance`.

Planned next:
- L1: bounded/segmented cache, then `WTinyLFUBalanceCacheL1`.
- L2: Redis-backed shared cache.

## Context
`GET /balance` is consistency-first and calculates balance from Postgres (`SUM(ledger_entries)`).
This is simple and correct, but the read cost grows with account history. The cache design keeps
freshness tied to `accounts.ledger_version`, not to TTL.

## Current Read Path
1. Load the account snapshot for `account_id + client_id`.
2. Read the current `ledger_version` from the account snapshot.
3. Try L1 `get_if_fresh(account_id, currency, expected_version)`.
4. On fresh hit, return the cached balance.
5. On miss, compute balance from Postgres and write the result into L1.

Negative results such as `ACCOUNT_NOT_FOUND` are not cached.

## Version Semantics
- A cache hit is valid only when `cached.ledger_version == expected_version`.
- If `cached.ledger_version < expected_version`, the entry is stale:
  return miss and remove it from L1.
- If `cached.ledger_version > expected_version`, return miss without invalidation.
- `put(...)` must never overwrite a newer cached version with an older one.

This keeps cache correctness aligned with the monotonic `accounts.ledger_version` model.

## Cache Contract
- `BalanceCacheWriteData`: data written by the use case into the cache.
- `BalanceCachedData`: stored/read cache entry with `updated_at_ts_ms`.
- `updated_at_ts_ms` is assigned by the adapter inside `put(...)`, not by the service layer.

## Keying
- Internal key format: `balance:{account_id}:{currency}`.
- Key construction lives inside cache adapters via a shared key builder.
- Application/service code works with domain fields (`account_id`, `currency`), not raw cache keys.

## Write Path Interaction
After a successful `process_payment`:
- `accounts.ledger_version` increments.
- Any older cached balance becomes stale by definition.

Freshness is still preserved because reads validate against the latest account version.

## Evolution Path
1. `VersionedMapCache`
   Baseline implementation for correctness and integration.
2. `SLRUBalanceCacheL1`
   Add eviction mechanics (`SLRU`) without changing the service contract.
3. `WTinyLFUBalanceCacheL1`
   Add frequency-aware admission and better memory efficiency.
4. Redis L2
   Add shared cross-instance cache while keeping the same version semantics.

## SLRU Behavior
`SLRUBalanceCacheL1`: It keeps the same version contract and changes only
the in-memory retention policy.

- A new key is inserted into the front of the `probation` segment.
- A fresh hit in `probation` promotes the entry to the front of `protected`.
- A fresh hit in `protected` moves the entry to the front of `protected`.
- If `protected` overflows, its tail is demoted to the front of `probation`.
- If `probation` overflows, its tail is evicted from L1.
- If `cached.ledger_version < expected_version`, return miss and remove the stale node.
- If `cached.ledger_version > expected_version`, return miss without removing the node.
- `put(...)` with an older version is ignored.
- `put(...)` with the same or newer version updates the cached value and is treated as access.

This stage is intentionally simpler than `W-TinyLFU`: it adds segmented retention and
promotion/demotion behavior first, before adding a window segment and frequency-based admission.
