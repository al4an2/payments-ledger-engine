import enum
from dataclasses import dataclass


class AccountNotFound(Exception):
    def __init__(self, message="Account Not Found"):
        super().__init__(message)
        self.code = "ACCOUNT_NOT_FOUND"


class InvalidAmount(Exception):
    def __init__(self, message="Not valid amount to debit/credit"):
        super().__init__(message)
        self.code = "INVALID_AMOUNT"


class InsufficientFunds(Exception):
    def __init__(self, message="Not enough funds to debit operation"):
        super().__init__(message)
        self.code = "INSUFFICIENT_FUNDS"


class CreditLimitExceeded(Exception):
    def __init__(self, message="Credit limit exceeded"):
        super().__init__(message)
        self.code = "CREDIT_LIMIT_EXCEEDED"


class InvalidAccountConfig(Exception):
    def __init__(self, message="Invalid Account Config"):
        super().__init__(message)
        self.code = "INVALID_ACCOUNT_CONFIG"


class AccountOwnershipError(Exception):
    def __init__(self, message="Difference owner of the account"):
        super().__init__(message)
        self.code = "ACCOUNT_OWNERSHIP_ERROR"


class EntryType(enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class BalanceType(enum.Enum):
    DEBIT_ONLY = "DEBIT_ONLY"
    CREDIT_ALLOWED = "CREDIT_ALLOWED"


@dataclass(frozen=True)
class LedgerDecision:
    signed_amount: int
    new_balance: int
    new_ledger_version: int
    entry_type: EntryType


def _decision(
    signed: int,
    new_balance: int,
    new_ledger_version: int,
    direction: EntryType,
) -> LedgerDecision:
    return LedgerDecision(
        signed_amount=signed,
        new_balance=new_balance,
        new_ledger_version=new_ledger_version,
        entry_type=direction,
    )


def decide_posting(
    amount: int,
    direction: EntryType,
    current_balance: int,
    balance_type: BalanceType,
    credit_limit: int | None,
    current_ledger_version: int,
) -> LedgerDecision:
    if amount <= 0:
        raise InvalidAmount()

    signed = amount if direction == EntryType.CREDIT else -amount
    new_balance = current_balance + signed
    new_ledger_version = current_ledger_version + 1

    if direction == EntryType.CREDIT:
        return _decision(signed, new_balance, new_ledger_version, direction)

    if new_balance >= 0:
        return _decision(signed, new_balance, new_ledger_version, direction)

    if balance_type == BalanceType.CREDIT_ALLOWED:
        if credit_limit is None or credit_limit < 0:
            raise InvalidAccountConfig()

        if new_balance < -credit_limit:
            raise CreditLimitExceeded()

        return _decision(signed, new_balance, new_ledger_version, direction)

    if balance_type == BalanceType.DEBIT_ONLY:
        raise InsufficientFunds()

    raise InvalidAccountConfig()
