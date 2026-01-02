# Payments Ledger Engine

**Production-like payments ledger with idempotency and versioned cache.**  

Work in progress — this project demonstrates an approach to **payments / infrastructure / data-heavy** systems.

---

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
- Docs: `db_schema.md`, `design.md`, `changelog.md`.
- Infrastructure: `docker-compose.yaml`.
- Data layer: `data_models/db_models.py`, `app_config/config.py`.
- Migrations: `alembic.ini`, `alembic/`, `alembic/versions/`.
- Tooling: `pyproject.toml`, `uv.lock`.

## What Exists Today
- Postgres runs via Docker Compose for local development.
- SQLAlchemy ORM models cover clients, accounts, ledger entries, and idempotency keys.
- Alembic is initialized with a baseline migration.

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
        └───────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │   Idempotency & Cache Layer   │
        │ - dedup index (TTL)           │
        │ - stored responses            │
        │ - L1 in-process cache         │
        │ - L2 Redis (phase 2)          │
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
