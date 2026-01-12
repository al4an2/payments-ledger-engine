import json
import hashlib
import time
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone

from payments_ledger.data_models.db_models import IdempotencyKey, IdempotencyStatus
from payments_ledger.api.main import PaymentRequest

class IdempotencyConflict(Exception):
    def __init__(self, message="Idempotency key reused with different payload"):
        super().__init__(message)
        self.code = "IDEMPOTENCY_CONFLICT"

class IdempotencyInProgress(Exception):
    def __init__(self, message="Idempotency key is already in progress"):
        super().__init__(message)
        self.code = "IDEMPOTENCY_IN_PROGRESS"

async def reserve_idempotency(session, client_id, idem_key, request_hash):
    async with session.begin():
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
                return row.response_payload

            if row.status == IdempotencyStatus.IN_PROGRESS:
                raise IdempotencyInProgress()

        return "succsess"
    
def make_request_hash(payload: PaymentRequest, client_id, idempotency_key) -> str:
    body = payload.model_dump(exclude_none=True)
    body.pop("request_id", None)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()