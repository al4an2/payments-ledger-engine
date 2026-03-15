# Changelog

## v 0.1.1 - 2026-03-15
- Repaired the older Alembic nullability migration to safely handle existing `NULL` values before applying stricter `NOT NULL` constraints.
- Added a new Alembic migration for database-level check constraints on `accounts` and `ledger_entries`.
- Added ORM-level `CheckConstraint` definitions for account configuration and ledger entry sign consistency.
- Tightened schema correctness so key invariants are enforced not only in application code and docs, but also in the database.


## v 0.1.0 - 2026-03-10
- Added initial in-process L1 balance cache (`VersionedMapCache`) and wired it into the `/balance` read path (`cache hit -> return`, `cache miss -> DB -> cache fill`).
- Refined cache contracts by splitting cache write input from stored cache entry (`BalanceCacheWriteData`, `BalanceCachedData`) and moving `updated_at_ts_ms` generation into cache adapters.
- Added unit tests for versioned cache semantics and read-path cache-hit coverage at the application/API level.
- Updated `docs/cache_versioning.md` and `README.md` to reflect the currently implemented cache stage and planned cache evolution.

## v 0.0.32 - 2026-02-28
- Added API-level `Idempotency-Key` format/length validation via dependency (`check_idem_key_format`) and covered invalid key scenarios with API tests.
- Added optimistic account version update behavior in ledger repository (`expected_ledger_version` guard) and integration coverage for version mismatch (`rowcount == 0` path).
- Added architecture and cache consistency documentation:
  - `docs/cache_vesrioning.md`

## v 0.0.31 - 2026-02-27
- Refactored API dependency wiring by centralizing providers in `src/payments_ledger/api/deps.py` (`get_uow`, `get_client_id`).
- Expanded `/payments` API tests with negative/error contract coverage (auth errors, domain failures, exception mapping).
- Refactored integration test setup: moved shared DB seed helpers into `tests/integration/conftest.py` and reused them across adapter/use-case tests.
- Added architecture and cache consistency documentation:
  - `docs/architecture.md`

## v 0.0.30 - 2026-02-27
- Added `/accounts/{account_id}` API flow (endpoint + service process) with tenant ownership checks.
- Added `AccountInfoResponse` contract and account result mapping for read operations (`OK`/`FAILED` + error codes).
- Expanded API tests for `/accounts` and `/balance` with stricter response contracts, auth error scenarios, and tenant-isolation cases.
- Updated unexpected exception logging to include error type for easier debugging.

## v 0.0.29 - 2026-02-08
- Added `/balance` API endpoint and processes from them.
- Added API tests for `/balance` success/error cases.
- Documented `/balance` usage and query parameters in README.

## v 0.0.28 - 2026-01-26
- Added PaymentResult DTO with idempotency status mapping (COMPLETED/FAILED).
- Logged unexpected API exceptions with request path for easier debugging.
- Updated README to reflect idempotency response status handling.

## v 0.0.27 - 2026-01-25
- Reorganized tests into layered folders (unit/integration/api) and split unit vs DB-backed tests.
- Added adapter/use-case integration test locations and removed duplicate domain test file.
- Updated README testing section to document the new structure and layer-specific runs.

## v 0.0.26 - 2026-01-24
- Added explicit `direction` to PaymentRequest and entry type conversion tests.
- Promoted ledger enums/errors to domain and added decision helper structure.
- Filled ledger repo account version update and balance query helpers.
- Updated README to reflect API contract and auth repo wiring.

## v 0.0.25 - 2026-01-24
- Added clean architecture ports and a SQLAlchemy Unit of Work for DB transactions.
- Implemented SQLAlchemy adapters for ledger, idempotency, and auth.
- Implemented ledger domain rules (EntryType/BalanceType, decision logic, invariants).
- Updated API wiring to use UoW and auth repo.
- Added/updated tests for auth and idempotency/payment wiring.

## v 0.0.24 - 2026-01-23
- Switched ORM models to SQLAlchemy 2.0 typed style (Mapped, DeclarativeBase).
- Added idempotency TTL handling via `expires_at`.
- Added ruff + mypy + bandit tooling and configuration notes.

## v 0.0.23 - 2026-01-23
- Added pytest setup with async fixtures and isolated test schema.
- Added idempotency and payments service tests.
- Documented testing workflow and TEST_DATABASE_URL usage.

## v 0.0.22 - 2026-01-23
- Wired payment orchestration with idempotency reserve/complete flow.
- Persisted PaymentResponse payloads for idempotent retries.
- Added API schemas (PaymentRequest/PaymentResponse) and request hashing.
- Enabled async DB session usage in services and API dependencies.

## v 0.0.21 - 2026-01-03
- Added idempotency service with optimistic insert and conflict handling.
- Added API auth helper for API key lookup.
- Added basic logging configuration.

## v 0.0.2 - 2026-01-02
- Organized code into `src/payments_ledger/` with api, config, data_models, cache, and ledger modules.
- Added FastAPI app skeleton with `/health`, `/balance/{account_id}`, and `/payments` endpoints.
- Added `docs/` directory for schema and design notes.
- Added `loadgen/` and `tests/` scaffolding directories.
- Expanded README with local setup and migration instructions.

## v 0.0.1 - 2026-01-01

- Happy New Year commit
- Documented planned DB schema and invariants in `db_schema.md`.
- Added architecture/design notes in `design.md`.
- Added Docker Compose setup for Postgres in `docker-compose.yaml`.
- Defined SQLAlchemy ORM models for core tables.
- Created initial Alembic migration scaffolding.
