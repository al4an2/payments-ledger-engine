from dataclasses import dataclass
from typing import Protocol, Literal, Any
from payments_ledger.ledger_domain.ledger_engine import EntryType, BalanceType
import enum


@dataclass(frozen=True)
class PaymentCommand:
    account_id: str
    amount: int
    currency: str
    direction: Literal["DEBIT", "CREDIT"]
    request_id: str | None = None


@dataclass(frozen=True)
class GetBalanceCommand:
    account_id: str
    currency: str
    request_id: str | None = None


@dataclass(frozen=True)
class GetAccountInfoCommand:
    account_id: str
    request_id: str


class IdempotencyState(enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class PaymentResult:
    payment_id: str | None
    status: IdempotencyState
    request_id: str
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "payment_id": self.payment_id,
            "status": self.status.value,
            "request_id": self.request_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class BalanceStatus(enum.Enum):
    OK = "OK"
    FAILED = "FAILED"


@dataclass(frozen=True)
class BalanceResult:
    account_id: str
    currency: str
    request_id: str
    balance: int | None
    status: BalanceStatus
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "currency": self.currency,
            "request_id": self.request_id,
            "balance": self.balance,
            "status": self.status.value,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


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

    async def complete(
        self, client_id: str, idem_key: str, response: dict, status: IdempotencyState
    ) -> IdemResult: ...


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    client_id: str
    ledger_version: int
    balance_type: BalanceType
    credit_limit: int | None


class LedgerRepo(Protocol):
    async def get_account_for_client(
        self, account_id: str, client_id: str
    ) -> AccountSnapshot | None: ...

    async def lock_account_for_client(
        self, account_id: str, client_id: str
    ) -> AccountSnapshot | None: ...

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
