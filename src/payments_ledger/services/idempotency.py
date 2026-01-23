import json
import hashlib
import time
from typing import Literal
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone
from dataclasses import dataclass

from payments_ledger.data_models.db_models import IdempotencyKey, IdempotencyStatus
from payments_ledger.api.schemas import PaymentRequest

class IdempotencyConflict(Exception):
    def __init__(self, message="Idempotency key reused with different payload"):
        super().__init__(message)
        self.code = "IDEMPOTENCY_CONFLICT"

class IdempotencyInProgress(Exception):
    def __init__(self, message= "Idempotency key is already in progress"):
        super().__init__(message)
        self.code = "IDEMPOTENCY_IN_PROGRESS"

@dataclass
class IdemResult:
    state: Literal["reserved", "duplicate"]
    response: dict | None = None

async def reserve_idempotency(session, client_id, idem_key, request_hash):
    stmt = (
        insert(IdempotencyKey)
        .values(
            client_id=client_id,
            idempotency_key=idem_key,
            request_hash=request_hash,
            status=IdempotencyStatus.IN_PROGRESS,
            expires_at=datetime.fromtimestamp(time.time() + 48 * 3600, tz=timezone.utc)
        )
        .on_conflict_do_nothing(
            index_elements=["client_id", "idempotency_key"]
        )
        .returning(IdempotencyKey.client_id)
    )
    result = await session.execute(stmt)
    inserted = result.scalar_one_or_none()
    
    if not inserted:
        row = (
            await session.execute(
                select(IdempotencyKey)
                .where(
                    IdempotencyKey.client_id == client_id,
                    IdempotencyKey.idempotency_key == idem_key,
                )
                .with_for_update()
            )
        ).scalar_one()

        if row.request_hash != request_hash:
            raise IdempotencyConflict()
        
        if row.status == IdempotencyStatus.COMPLETED:
            return IdemResult("duplicate", row.response_payload)

        if row.status == IdempotencyStatus.IN_PROGRESS:
            raise IdempotencyInProgress()

        if row.status == IdempotencyStatus.FAILED:
            return IdemResult("duplicate", row.response_payload)

    return IdemResult("reserved")

async def complete_idempotency(session, client_id, idem_key, response):
    stmt = (
        update(IdempotencyKey)
        .where(
            IdempotencyKey.client_id == client_id,
            IdempotencyKey.idempotency_key == idem_key,
            IdempotencyKey.status == IdempotencyStatus.IN_PROGRESS
        )
        .values(
            status=IdempotencyStatus.COMPLETED,
            response_payload=response,
        )
        .on_conflict_do_nothing(
            index_elements=["client_id", "idempotency_key"]
        )
        .returning(IdempotencyKey.client_id)
    )
    result = await session.execute(stmt)

    if result.rowcount == 0:
        row = (
            await session.execute(
                select(IdempotencyKey)
                .where(
                    IdempotencyKey.client_id == client_id,
                    IdempotencyKey.idempotency_key == idem_key,
                )
            )
        ).scalar_one_or_none()
        
        if row is None:
            raise RuntimeError("Idempotency complete failed: not_exist")
    
        if row.status == IdempotencyStatus.COMPLETED:
            return IdemResult("duplicate", row.response_payload)

        if row.status == IdempotencyStatus.FAILED:
            return IdemResult("duplicate", row.response_payload)
        
        raise RuntimeError("Unexpected error")

    return None
    
def make_request_hash(payload: PaymentRequest) -> str:
    body = payload.model_dump(exclude_none=True)
    body.pop("request_id", None)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()