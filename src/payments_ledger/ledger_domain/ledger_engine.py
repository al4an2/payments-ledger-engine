import enum


class AccountNotFound(Exception):
    def __init__(self, message="Account Not Found"):
        super().__init__(message)
        self.code = "ACCOUNT_NOT_FOUND"


class EntryType(enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
