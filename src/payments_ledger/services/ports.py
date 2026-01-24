from dataclasses import dataclass
from typing import Protocol, Literal


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
