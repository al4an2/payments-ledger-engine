# Versioned Balance Cache

## Status
Implemented now:
- Active L1: in-process `SLRUBalanceCacheL1` wired into `GET /balance`.
- Previous baseline L1: `VersionedMapCache`, kept as the earlier correctness-first stage.

Planned next:
- L1: `WTinyLFUBalanceCacheL1`.
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
   Active bounded/segmented L1 implementation with `probation` / `protected` retention.
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

## W-TinyLFU Behavior
- A new key is inserted into the front of `window`.
- A fresh hit in `window` refreshes recency inside `window` only.
- If `window` overflows, its tail becomes the admission candidate.
- If `probation` has free space, the candidate is inserted into `probation`.
- If `probation` is full, the candidate is compared with the `probation` tail victim by sketch estimate.
- The candidate is admitted only when `candidate_frequency > victim_frequency`.
- Equal frequency rejects the candidate and keeps the victim.
- A fresh hit in `probation` promotes the entry to `protected`.
- A fresh hit in `protected` refreshes recency inside `protected`.
- If `protected` overflows, its tail is demoted to the front of `probation`.

## W-TinyLFU Sketch Decisions
The `WTinyLFUBalanceCacheL1` stage uses a separate `_FrequencySketch` for admission decisions. The current design choices are:

- frequency is tracked in a compact Count-Min-style counter table, not as exact per-key counts
- the sketch defaults to four seeds inspired by the Caffeine implementation, while still allowing seed override for experimentation
- width is validated as a power of two so bucket indexing can use a bit mask
- counters are saturating, with the default `max_counter = 15` chosen in the spirit of the compact Caffeine sketch
- counters are periodically halved to age old hot keys and keep the sketch adaptive
- admission policy: admit the candidate only when `candidate_frequency > victim_frequency`; equal frequency rejects the candidate

This keeps frequency estimation separate from cache segments:
- `window` / `probation` / `protected` keep recency and retention state
- `_FrequencySketch` provides approximate popularity estimates for candidate-vs-victim admission

## W-TinyLFU Capacity Split
The current `WTinyLFUBalanceCacheL1` design treats `window` as a front-door segment that is carved out before the main `SLRU` area:

- `window_capacity` is derived from total `capacity` using `window_ratio`
- `window` is clamped to at least one slot so admission always has a real staging area
- `main_capacity = capacity - window_capacity`
- `protected_ratio` is applied to `main_capacity`, not to the full cache size
- `probation_capacity` is the remainder of `main_capacity` after `protected_capacity`

This keeps the total bounded by the configured cache capacity while making the role of each segment
explicit:
- `window` handles short-term admission for new entries
- `probation` and `protected` remain the retained main-cache area
