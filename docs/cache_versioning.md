# Versioned Balance Cache (L1 + L2)

## Status
Proposed

## Context
`GET /balance` currently reads from Postgres (`SUM(ledger_entries)`), which is consistent but expensive at scale.

## Decision
Use a two-layer cache:
- L1: in-process cache for ultra-fast local hits.
- L2: Redis for shared cross-instance hits.

Cache correctness is version-based:
- Source of truth for freshness is `accounts.ledger_version`.
- A cache entry is valid only when:
  `cached.ledger_version == current_account.ledger_version`.

## Key and Value Contract
- Key: `balance:{account_id}:{currency}` (`currency` normalized to uppercase).
- Value fields: `account_id`, `currency`, `balance`, `ledger_version`, `updated_at_ts_ms`.

## Read Path
1. Read current account version.
2. Try L1 with expected version.
3. On miss, try L2 with expected version.
4. On miss/stale, read DB and repopulate L2 then L1.

## Write Path
After successful `process_payment`:
- `accounts.ledger_version` increments.
- Previous cache entries are stale by definition.

## Operational Policy
Redis TTL is optional and used for memory/cleanup only.
TTL is not a consistency mechanism.

## Consequences
Pros:
- Strong consistency semantics with low read latency.
- Safe under retries and delayed invalidation.

Trade-off:
- Extra read step to load current version before cache validation.
