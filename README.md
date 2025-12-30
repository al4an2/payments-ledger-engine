# Payments Ledger Engine

**Production-like payments ledger with idempotency and versioned cache.**  

Work in progress — this project demonstrates a senior-level SWE approach to **payments / infrastructure / data-heavy** systems.

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
