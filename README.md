# Payments Ledger Engine

**Correctness-focused payments backend with idempotent writes, append-only ledger accounting, and version-aware balance caching.**

## Why It Is Hard
- Exactly-once-oriented payment handling under retries, duplicate requests, and concurrent callers.
- Correct balance reads over append-only ledger history without serving stale cached versions.
- Consistency across API contracts, service orchestration, database constraints, and cache admission/retention policy.

## What this project demonstrates

- Designing correctness-sensitive write paths with transactional boundaries
- Handling retries, duplicate requests, and stale-cache reads safely
- Evolving internal architecture while preserving API and data invariants

## What Is Already Proven
- `/payments`, `/balance`, and `/accounts` flows are implemented with FastAPI, SQLAlchemy, and an explicit Unit of Work boundary.
- `WTinyLFUBalanceCacheL1` is wired into `/balance` with `window` / `probation` / `protected` segments and `ledger_version`-based freshness checks.
- Unit, integration, and API tests cover cache semantics, idempotency flow, DB constraints, and read/write contract behavior.

## System Sketch
```text
POST /payments
  -> idempotency reserve / replay
  -> append-only ledger write
  -> account.ledger_version increments

GET /balance
  -> WTinyLFU L1 fresh hit -> return
  -> stale hit or miss -> Postgres SUM(amount) -> cache fill -> return
```

## Failure Modes Covered
- Duplicate payment requests via idempotency reserve / replay flow.
- Stale cache entries removed on `accounts.ledger_version` mismatch.
- Older cache writes rejected; newer cached values are not overwritten by stale data.
- Optimistic account version guard for conflicting ledger updates.
- Database check constraints for account configuration and signed ledger-entry invariants.

## Current State
- Docs: `docs/db_schema.md`, `docs/design.md`, `docs/architecture.md`, `docs/cache_versioning.md`, `changelog.md`.
- Infrastructure: `Dockerfile`, `docker-compose.yaml`, `.env`.
- API: FastAPI app with `/health`, `/balance/{account_id}` (currency query), `/accounts/{account_id}`, `/payments` (explicit `direction`).
- API dependencies: centralized providers in `src/payments_ledger/api/deps.py` (`get_uow`, `get_client_id`).
- Application: payment orchestration + idempotency reserve/complete via ports.
- Domain: ledger decision logic (invariants, credit limits, entry types).
- Adapters: SQLAlchemy repos for idempotency, ledger, and auth.
- Data layer: SQLAlchemy 2.0 typed ORM models in `src/payments_ledger/data_models/`.
- Unit of Work: DB transaction boundary in `adapters/db/uow.py`.
- Migrations: `alembic.ini`, `alembic/`, `alembic/versions/`.
- Tooling: `pyproject.toml`, `uv.lock` (ruff, mypy, bandit).

## What Exists Today
- The service can run either directly via `uvicorn` or as a containerized app with Postgres via Docker Compose.
- The app container applies `alembic upgrade head` before starting `uvicorn`, so local containerized startup keeps schema and runtime aligned.
- The database layer now enforces key invariants with explicit check constraints.
- SQLAlchemy ORM models cover clients, accounts, ledger entries, and idempotency keys.
- Async DB session setup + config helpers for DB URLs.
- Idempotency flow via repo adapter (reserve/complete) stores response payloads for exact retries.
- API validates `Idempotency-Key` format/length in dependency layer before service execution.
- Application returns a typed `PaymentResult` DTO; idempotency stores `COMPLETED`/`FAILED` outcomes.
- Idempotency keys have `expires_at` TTL; completed keys are always replayed, in‑progress keys can expire.
- Ledger domain rules (debit/credit, limits) implemented; SQL adapter supports lock/get_balance/insert/update.
- Ledger entries store signed balance effect in `amount`: `CREDIT` is positive, `DEBIT` is negative, so balance reads use `SUM(amount)`.
- Account version update supports optimistic guard (`expected_ledger_version`) for safer concurrent write detection.
- Payments service orchestrates idempotency + ledger write path integration.
- Alembic history now includes a forward migration that aligns DB-level defaults with current ORM expectations for `ledger_version`, `status`, and `created_at`.
- Cache contracts separate write input from stored cache entry (`BalanceCacheWriteData` vs `BalanceCachedData`), so adapters own cache metadata such as `updated_at_ts_ms`.
- `/balance` read path uses an in-process `WTinyLFUBalanceCacheL1` with `window` / `probation` / `protected` segments, sketch-based admission, `ledger_version` freshness checks, and miss -> DB -> cache fill behavior.
- `SLRUBalanceCacheL1` remains in the repository as the earlier segmented L1 stage, and `VersionedMapCache` remains as the initial correctness-first baseline.
- FastAPI app with auth repo (API key → client_id) and PaymentRequest/PaymentResponse schemas.
- Account info read path (`/accounts/{account_id}`) returns account configuration (`balance_type`, `credit_limit`) with tenant isolation.
- API response schemas use stricter literal status/value contracts for read/write endpoints.
- Alembic initialized with baseline migration.

## Cache Status
- Implemented now:
  - `W-TinyLFU`-style in-process L1 cache (`WTinyLFUBalanceCacheL1`) for `GET /balance`
  - exact version-match freshness checks via `accounts.ledger_version`
  - `window` / `probation` / `protected` retention behavior inside the active L1 adapter
  - `_FrequencySketch`-based admission with saturating counters and periodic aging
  - unit coverage for `WTinyLFUBalanceCacheL1` behavior, plus retained coverage for earlier cache stages
- Planned next:
  - Redis L2

## Local Setup
1) Install dependencies:
```bash
uv sync --extra dev
```

2) Start Postgres:
```bash
docker compose up -d
```

3) Run migrations:
```bash
uv run alembic upgrade head
```

4) Run API (development):
```bash
uv run uvicorn payments_ledger.api.main:app --reload --app-dir src
```

Alternative: run app + Postgres in containers:
```bash
docker compose up --build
```

5) Example requests:
```bash
curl -X POST "http://127.0.0.1:8000/payments" \
  -H "Authorization: Bearer <api_key>" \
  -H "Idempotency-Key: idem-001" \
  -H "Content-Type: application/json" \
  -d '{"account_id":"acc_1","amount":1000,"currency":"EUR","direction":"DEBIT","request_id":"req-1"}'

curl -X GET "http://127.0.0.1:8000/balance/acc_1?currency=EUR" \
  -H "Authorization: Bearer <api_key>" \
  -H "X-Request-Id: req-2"

curl -X GET "http://127.0.0.1:8000/accounts/acc_1" \
  -H "Authorization: Bearer <api_key>" \
  -H "X-Request-Id: req-3"
```

## Migrations
Create a new revision (autogenerate from ORM models):
```bash
uv run alembic revision --autogenerate -m "your message"
```

Apply migrations:
```bash
uv run alembic upgrade head
```

Check current revision:
```bash
uv run alembic current
```

## Testing
Tests are split by layer to mirror clean architecture:

- `tests/unit/` — pure unit tests (domain + application, no DB).
- `tests/integration/` — SQLAlchemy adapters and DB-backed use cases.
- `tests/api/` — API contract tests.

Tests use a **separate test database URL** and create a **temporary schema** per test run, so your real tables are not touched.

1) Set a test DB URL (prefer a dedicated DB):
```bash
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/payments_ledger_test"
```

2) Run all tests:
```bash
uv run pytest
```

Or run by layer:
```bash
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/api
```

Notes:
- If you don’t want to create a separate database, you can point `TEST_DATABASE_URL` to the same DB. Tests will still use an isolated schema.
- Tables are created via ORM metadata for tests (not Alembic).
- API tests cover success/error contracts, auth header validation, and tenant-isolation cases for read endpoints.
- Integration tests use shared seed fixtures from `tests/integration/conftest.py` to avoid setup duplication.

## Code Quality
Run lint + format:
```bash
uv run ruff check .
uv run ruff format .
```

Run type checks:
```bash
uv run mypy src
```

Optional security scan:
```bash
uv run bandit -r src -x tests,alembic/versions
```

## Architecture:

            ┌───────────────────────┐
            │   Load Generator      │
            │ (retries, races,      │
            │  duplicate requests)  │
            └───────────────────────┘
                        │ HTTP
                        ▼
        ┌───────────────────────────────────┐
        │           Payments API            │
        │ - request validation              │
        │ - idempotency key extraction      │
        │ - auth repo                        │
        │ - calls service layer             │
        └───────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │     Services / Ports          │
        │ - idempotency reserve/complete│
        │ - ledger orchestration        │
        │ - domain decisions            │
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │     Ledger Engine & Adapters / DB     │
        │ - append-only ledger                  │
        │ - per-account serialization           │
        │ - balance versioning                  │
        │ - invariants                          │
        │ - SQLAlchemy repos                    │
        │ - UoW transaction boundary            │
        └───────────────┬───────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │        Postgres       │
            │ - ledger_entries      │
            │ - accounts            │
            │ - idempotency_keys    │
            │ - constraints / WAL   │
            └───────────────────────┘ 
