# Planned DB Schema (Draft)

This schema is planned and may evolve as the implementation lands. The ledger is the source of truth; balances are derived from `ledger_entries` and cached with a version check.

Core tables:
- `accounts` - account metadata + invariants + per-account serialization anchor
- `ledger_entries` - append-only ledger (source of truth)
- `idempotency_keys` - request-level exactly-once semantics

## 1) accounts - account metadata + invariants

Role:
- Holds account rules (debit-only vs. credit-allowed)
- Stores `ledger_version` used for cache version checks and per-account serialization

Planned schema:
```sql
CREATE TABLE accounts (
  account_id        TEXT PRIMARY KEY,

  ledger_version    BIGINT NOT NULL DEFAULT 0,

  balance_type      TEXT NOT NULL
    CHECK (balance_type IN ('DEBIT_ONLY', 'CREDIT_ALLOWED')),

  credit_limit      BIGINT, -- NULL for DEBIT_ONLY

  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

  CHECK (
    (balance_type = 'DEBIT_ONLY' AND credit_limit IS NULL) OR
    (balance_type = 'CREDIT_ALLOWED' AND credit_limit IS NOT NULL)
  )
);
```

Invariants:
- `ledger_version` is monotonically increasing per account
- Balance is not stored here (derived from `ledger_entries`)
- Credit rules are enforced in the write transaction

## 2) ledger_entries - append-only ledger (domain level)

Role:
- Source of truth for money movement
- Strictly ordered state transitions per account
- Supports audit/replay

Planned schema:
```sql
CREATE TABLE ledger_entries (
  entry_id          BIGSERIAL PRIMARY KEY,

  account_id        TEXT NOT NULL REFERENCES accounts(account_id),

  ledger_version    BIGINT NOT NULL,

  amount            BIGINT NOT NULL, -- negative = debit, positive = credit
  currency          TEXT NOT NULL,

  entry_type        TEXT NOT NULL
    CHECK (entry_type IN ('DEBIT', 'CREDIT')),

  request_id        TEXT NOT NULL, -- logical request identifier (trace)

  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (account_id, ledger_version),

  CHECK (
    (entry_type = 'DEBIT' AND amount < 0) OR
    (entry_type = 'CREDIT' AND amount > 0)
  )
);
```

Notes:
- No idempotency logic here; dedup lives in `idempotency_keys`
- `request_id` is for tracing only (not a dedup key)
- If accounts are single-currency, currency can move to `accounts` in a later revision

## 3) idempotency_keys - request-level idempotency (API layer)

Role:
- Exactly-once HTTP semantics
- Safe retries with identical responses

Planned schema:
```sql
CREATE TABLE idempotency_keys (
  client_id          TEXT NOT NULL,
  idempotency_key    TEXT NOT NULL,

  request_hash       TEXT NOT NULL,
  response_code      INT,
  response_payload   JSONB,

  status             TEXT NOT NULL
    CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')),

  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at         TIMESTAMPTZ,

  PRIMARY KEY (client_id, idempotency_key)
);
```

Invariants:
- Scoped by `(client_id, idempotency_key)`
- Every mutating request passes through this table in the same DB transaction
- A mismatched `request_hash` returns a conflict response

Operational note:
- `expires_at` is optional; for payments, keep long retention to avoid double spends on late retries
