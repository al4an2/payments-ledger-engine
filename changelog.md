# Changelog

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
