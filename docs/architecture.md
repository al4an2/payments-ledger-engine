# Architecture (Current State)

This document describes the architecture that is implemented now.
It focuses on what already works in code, not future design ideas.

## 1) High-Level Structure

The project follows a layered approach:

- `api/` - FastAPI endpoints, HTTP validation, exception mapping, DI wiring.
- `services/` - application orchestration and ports.
- `ledger_domain/` - domain rules for posting decisions and invariants.
- `adapters/db/` - SQLAlchemy implementations of repository ports + Unit of Work.
- `data_models/` - SQLAlchemy ORM models.
- `db/` - DB session/engine factory.

The API layer calls service functions through ports and a Unit of Work.

## 2) Runtime Components

- **FastAPI app**: `src/payments_ledger/api/main.py`
- **Dependencies (composition root)**: `src/payments_ledger/api/deps.py`
  - `get_uow`
  - `get_client_id` (aliased to `get_client_id_auth`)
- **Auth HTTP dependency**: `src/payments_ledger/api/auth.py`
- **Application services**: `src/payments_ledger/services/payments.py`
- **Domain decision engine**: `src/payments_ledger/ledger_domain/ledger_engine.py`
- **Adapters**:
  - `SqlAlchemyUnitOfWork`
  - `SqlAlchemyLedgerRepo`
  - `SqlAlchemyIdempotencyRepo`
  - `SqlAlchemyAuthRepo`

## 3) Main Flows

### 3.1 `POST /payments`

1. API validates payload and reads `Idempotency-Key`.
2. API resolves `client_id` from bearer token.
3. API calls `process_payment(...)`.
4. Service reserves idempotency key (`IN_PROGRESS` or duplicate/conflict/in-progress paths).
5. Service locks account row (`SELECT ... FOR UPDATE`) for tenant/account pair.
6. Service loads current balance and calls domain `decide_posting(...)`.
7. Service writes `ledger_entries` row and updates `accounts.ledger_version`.
8. Service completes idempotency record with final response (`COMPLETED` or `FAILED`).
9. API returns typed response contract.

### 3.2 `GET /balance/{account_id}`

1. API validates input and resolves `client_id`.
2. API calls `balance_process(...)`.
3. Service verifies account ownership (`account_id + client_id`).
4. Service reads `accounts.ledger_version` from the account snapshot.
5. Service asks the in-process L1 cache for an exact-version hit.
6. On L1 hit, the cached balance is returned immediately.
7. On miss, service calculates balance from ledger entries and fills L1.
8. API returns `OK` or `FAILED` contract.

### 3.3 `GET /accounts/{account_id}`

1. API validates input and resolves `client_id`.
2. API calls `account_info_process(...)`.
3. Service verifies account ownership.
4. Service returns account configuration (`balance_type`, `credit_limit`) or `FAILED`.

## 4) Data Consistency Model

- **Source of truth**: `ledger_entries` (append-only for movements).
- **Account state anchor**: `accounts.ledger_version`.
- **Uniqueness**: `(account_id, ledger_version)` is unique in ledger entries.
- **Idempotency scope**: `(client_id, idempotency_key)` is unique.
- **Transaction boundary**: Unit of Work opens one DB transaction for service operations.

Current write path guarantees:

- one posting decision per request execution,
- monotonic account version updates,
- idempotent retry behavior through stored response payloads.

Current read-cache guarantees:

- `/balance` uses an in-process L1 cache behind the `BalanceCacheL1` port.
- A cache hit is valid only when `cached.ledger_version == expected_version`.
- Older cached versions are treated as stale and removed.
- Newer cached versions are treated as misses without invalidation.
- The currently wired implementation is `SLRUBalanceCacheL1`.

## 5) Error and Contract Strategy

- Domain/application errors are returned as business `FAILED` responses where expected.
- Idempotency protocol errors are mapped to `409`:
  - `IDEMPOTENCY_CONFLICT`
  - `IDEMPOTENCY_IN_PROGRESS`
- Unexpected errors are mapped by global handler to `500 {"detail": "INTERNAL_ERROR"}`.
- API schemas use strict literals for statuses and key enums.

## 6) Testing Architecture

Tests are split by layer:

- `tests/unit/` - pure domain/application unit tests.
- `tests/integration/` - DB-backed adapters/use-cases.
- `tests/api/` - endpoint contracts (status/body/auth/error mapping).

Integration tests share DB seed fixtures via `tests/integration/conftest.py`.

## 7) Not Yet Implemented

- Redis-backed L2 cache is still planned and not integrated yet.
- `WTinyLFU`-based L1 is still planned and not integrated yet.
- Load generator (Go) is planned as a separate workload/testing component.
