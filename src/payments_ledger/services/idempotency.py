from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from payments_ledger.data_models.db_models import IdempotencyKey, IdempotencyStatus


class IdempotencyConflict(Exception):
    def __init__(self, message="Idempotency key reused with different payload"):
        super().__init__(message)
        self.code = "IDEMPOTENCY_CONFLICT"

class IdempotencyInProgress(Exception):
    def __init__(self, message="Idempotency key is already in progress"):
        super().__init__(message)
        self.code = "IDEMPOTENCY_IN_PROGRESS"

async def handle_payment(session, client_id, idem_key, request_hash):
    async with session.begin():
        stmt = (
            insert(IdempotencyKey)
            .values(
                client_id=client_id,
                idempotency_key=idem_key,
                request_hash=request_hash,
                status=IdempotencyStatus.IN_PROGRESS,
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

        return result