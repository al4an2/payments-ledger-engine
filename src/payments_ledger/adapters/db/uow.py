from payments_ledger.adapters.db.idempotency_repo import SqlAlchemyIdempotencyRepo
from payments_ledger.adapters.db.ledger_repo import SqlAlchemyLedgerRepo


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def __aenter__(self):
        self.session = self._session_factory()
        self._tx = await self.session.begin()
        self.idempotency_repo = SqlAlchemyIdempotencyRepo(self.session)
        self.ledger_repo = SqlAlchemyLedgerRepo(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            await self._tx.rollback()
        else:
            await self._tx.commit()
        await self.session.close()

    async def commit(self) -> None:
        await self._tx.commit()

    async def rollback(self) -> None:
        await self._tx.rollback()
