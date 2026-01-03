# Changelog

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
