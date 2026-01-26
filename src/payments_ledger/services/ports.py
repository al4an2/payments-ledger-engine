from dataclasses import dataclass
from typing import Protocol, Literal
from payments_ledger.ledger_domain.ledger_engine import EntryType, BalanceType
import enum


@dataclass(frozen=True)
class PaymentCommand:
    account_id: str
    amount: int
    currency: str
    direction: Literal["DEBIT", "CREDIT"]
    request_id: str | None = None


class IdempotencyState(enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IdempotencyConflict(Exception):
    def __init__(self, message="Idempotency key reused with different payload"):
        super().__init__(message)
        self.code = "IDEMPOTENCY_CONFLICT"


class IdempotencyInProgress(Exception):
    def __init__(self, message="Idempotency key is already in progress"):
        super().__init__(message)
        self.code = "IDEMPOTENCY_IN_PROGRESS"


@dataclass(frozen=True)
class IdemResult:
    state: Literal["reserved", "duplicate", "completed"]
    response: dict | None = None


class IdempotencyRepo(Protocol):
    async def reserve(self, client_id: str, idem_key: str, request_hash: str) -> IdemResult: ...

    async def complete(self, client_id: str, idem_key: str, response: dict) -> IdemResult: ...


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    client_id: str
    ledger_version: int
    balance_type: BalanceType
    credit_limit: int | None


class LedgerRepo(Protocol):
    async def lock_account(self, account_id: str) -> AccountSnapshot | None: ...

    async def get_balance(self, account_id: str, currency: str) -> int: ...

    async def insert_entry(
        self,
        account_id: str,
        ledger_version: int,
        amount: int,
        currency: str,
        entry_type: EntryType,
        request_id: str,
    ) -> None: ...

    async def update_account_version(self, account_id: str, ledger_version: int) -> None: ...


class UnitOfWork(Protocol):
    idempotency_repo: IdempotencyRepo
    ledger_repo: LedgerRepo

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class AuthRepo(Protocol):
    async def get_client_id_by_api_key_hash(self, api_key_hash: str) -> str | None: ...
