from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from payments_ledger.data_models.db_models import IdempotencyKey, IdempotencyStatus
from payments_ledger.services.ports import (
    IdemResult,
    IdempotencyConflict,
    IdempotencyInProgress,
)


class SqlAlchemyIdempotencyRepo:
    def __init__(self, session, ttl_hours: int = 48) -> None:
        self.session = session
        self.ttl_hours = ttl_hours

    async def _reset_to_in_progress(
        self, client_id, idem_key, request_hash, new_expires_at
    ) -> IdemResult:
        await self.session.execute(
            update(IdempotencyKey)
            .where(
                IdempotencyKey.client_id == client_id,
                IdempotencyKey.idempotency_key == idem_key,
            )
            .values(
                request_hash=request_hash,
                status=IdempotencyStatus.IN_PROGRESS,
                response_payload=None,
                expires_at=new_expires_at,
            )
        )

        return IdemResult("reserved")

    async def reserve(self, client_id: str, idem_key: str, request_hash: str) -> IdemResult:
        now = datetime.now(timezone.utc)
        new_expires_at = now + timedelta(hours=self.ttl_hours)

        stmt = (
            insert(IdempotencyKey)
            .values(
                client_id=client_id,
                idempotency_key=idem_key,
                request_hash=request_hash,
                status=IdempotencyStatus.IN_PROGRESS,
                expires_at=new_expires_at,
            )
            .on_conflict_do_nothing(index_elements=["client_id", "idempotency_key"])
            .returning(IdempotencyKey.client_id)
        )
        result = await self.session.execute(stmt)
        inserted = result.scalar_one_or_none()

        if not inserted:
            row = (
                await self.session.execute(
                    select(IdempotencyKey)
                    .where(
                        IdempotencyKey.client_id == client_id,
                        IdempotencyKey.idempotency_key == idem_key,
                    )
                    .with_for_update()
                )
            ).scalar_one()

            if row.status == IdempotencyStatus.COMPLETED:
                if row.request_hash != request_hash:
                    raise IdempotencyConflict()
                return IdemResult("duplicate", row.response_payload)

            if row.expires_at and row.expires_at <= now:
                return await self._reset_to_in_progress(
                    client_id, idem_key, request_hash, new_expires_at
                )

            if row.request_hash != request_hash:
                raise IdempotencyConflict()

            if row.status == IdempotencyStatus.IN_PROGRESS:
                raise IdempotencyInProgress()

            if row.status == IdempotencyStatus.FAILED:
                return IdemResult("duplicate", row.response_payload)

        return IdemResult("reserved")

    async def complete(self, client_id: str, idem_key: str, response: dict) -> IdemResult:
        stmt = (
            update(IdempotencyKey)
            .where(
                IdempotencyKey.client_id == client_id,
                IdempotencyKey.idempotency_key == idem_key,
                IdempotencyKey.status == IdempotencyStatus.IN_PROGRESS,
            )
            .values(
                status=IdempotencyStatus.COMPLETED,
                response_payload=response,
            )
        )
        result = await self.session.execute(stmt)

        if result.rowcount == 0:
            row = (
                await self.session.execute(
                    select(IdempotencyKey).where(
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

        return IdemResult("completed")
