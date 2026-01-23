# Payments Ledger Engine

**Production-like payments ledger with idempotency and versioned cache.**  

Work in progress — this project demonstrates an approach to **payments / infrastructure / data-heavy** systems.

---

**Current status**: Core API + idempotency flow working, ledger engine stub in progress

## Project Goal

Build a service that:

- Processes payments with **exactly-once** semantics.
- Maintains an **append-only ledger**.
- Supports **idempotency** for requests.
- Uses **versioned cache** (L1 in-process + L2 Redis) to speed up reads.
- Provides APIs for balances and payments.

This project demonstrates:

- Thoughtful **system design**
- Safe handling of **stateful transactions**
- **Correctness** under retries and race conditions

Planned database schema: `db_schema.md`.

## Current State
- Docs: `docs/db_schema.md`, `docs/design.md`, `changelog.md`.
- Infrastructure: `docker-compose.yaml`, `.env`.
- API: FastAPI app with `/health`, `/balance/{account_id}`, `/payments`.
- Services: payment orchestration + idempotency reserve/complete.
- Data layer: SQLAlchemy 2.0 typed ORM models in `src/payments_ledger/data_models/`.
- Migrations: `alembic.ini`, `alembic/`, `alembic/versions/`.
- Tooling: `pyproject.toml`, `uv.lock` (ruff, mypy, bandit).

## What Exists Today
- Postgres runs via Docker Compose for local development.
- SQLAlchemy ORM models cover clients, accounts, ledger entries, and idempotency keys.
- Async DB session setup + config helpers for DB URLs.
- Idempotency service (reserve/complete) stores response payloads for exact retries.
- Idempotency keys have `expires_at` TTL; completed keys are always replayed, in‑progress keys can expire.
- Payments service orchestrates idempotency + (stub) ledger logic.
- FastAPI app with auth stub (API key → client_id) and PaymentRequest/PaymentResponse schemas.
- Alembic initialized with baseline migration.

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

5) Example request:
```bash
curl -X POST "http://127.0.0.1:8000/payments" \
  -H "Authorization: Bearer <api_key>" \
  -H "Idempotency-Key: idem-001" \
  -H "Content-Type: application/json" \
  -d '{"account_id":"acc_1","amount":1000,"currency":"EUR","request_id":"req-1"}'
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
Tests use a **separate test database URL** and create a **temporary schema** per test run, so your real tables are not touched.

1) Set a test DB URL (prefer a dedicated DB):
```bash
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/payments_ledger_test"
```

2) Run tests:
```bash
uv run pytest
```

Notes:
- If you don’t want to create a separate database, you can point `TEST_DATABASE_URL` to the same DB. Tests will still use an isolated schema.
- Tables are created via ORM metadata for tests (not Alembic).

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
        │ - auth (stub)                     │
        │ - calls service layer             │
        └───────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │     Service / Idempotency     │
        │ - reserve/complete            │
        │ - stored responses            │
        │ - dedup index (TTL)           │
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │           Ledger Engine               │
        │ - append-only ledger                  │
        │ - per-account serialization           │
        │ - balance versioning                  │
        │ - invariants (no negative balance)    │
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
