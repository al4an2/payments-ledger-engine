import enum


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


class EntryType(enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class BalanceType(enum.Enum):
    DEBIT_ONLY = "DEBIT_ONLY"
    CREDIT_ALLOWED = "CREDIT_ALLOWED"


async def decide_posting():
    pass
