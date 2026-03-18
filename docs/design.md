# Design Notes

## Problem Statement

This project models the core of a payment ledger system built around append-only semantics.

The goal is to process financial operations in a way that favors correctness, replay safety,
and auditability over maximum availability or lowest-latency reads.

In financial systems, consistency is more important than availability. A delayed or rejected
response is usually better than an incorrect balance, a duplicated charge, or a state that
cannot be explained later.

Account state is derived from ledger entries instead of being overwritten in place. This makes
it easier to reason about history, retries, concurrent operations, and correctness.

The project focuses on the application core of such a system:
idempotent payment processing, tenant-safe balance reads, account configuration reads,
transaction boundaries, and version-based cache correctness.

## Key Risks

The design treats the following risks as important:

- duplicate payment caused by client retry, network retry, or replay
- conflicting replay where the same idempotency key is reused with a different payload
- concurrent writes on the same account causing lost updates or incorrect balances
- stale cache returning an incorrect balance after `ledger_version` changes
- reading another tenant's account or balance because of missing ownership checks
- partial failure between ledger mutation and idempotency completion
- non-deterministic replay result for the same idempotency key
- broken business invariants, for example invalid amount handling or debit below allowed limits
- inconsistent ledger rows where `entry_type` and stored `amount` do not describe the same effect

## Designs

The current ledger storage model keeps `amount` as a signed value:
- `CREDIT` entries are stored with positive `amount`
- `DEBIT` entries are stored with negative `amount`

This allows balance reads to use a simple `SUM(amount)` query. The operation type is still kept
in `entry_type`, so the database can validate that the stored sign and the entry type agree.

## Cache Evolution Strategy

The cache work is intentionally split into several versions:

1. `VersionedMapCache`
2. `SLRUBalanceCacheL1`
3. `WTinyLFUBalanceCacheL1`

This sequence is deliberate.

`VersionedMapCache` is the correctness-first baseline. It proves that balance caching can be
integrated safely with exact `ledger_version` matching before any eviction policy is introduced.

`SLRUBalanceCacheL1` is the next step because it adds segmented retention (`probation` and
`protected`) without adding frequency estimation at the same time. This keeps the mental model
small enough to test and reason about.

`WTinyLFUBalanceCacheL1` comes after that because it builds on top of the same ideas and adds
more complex pieces: a window segment and frequency-based admission. Implementing it directly
would make it harder to separate correctness bugs from policy bugs.

For this project, the staged approach is better than jumping to the final algorithm immediately:
- each cache stage remains understandable on its own
- the public service contract stays stable while only the adapter changes
- tests can prove behavior incrementally
- the repository shows the design evolution clearly, which is useful for a portfolio project
