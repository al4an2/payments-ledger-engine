from sqlalchemy import select
from payments_ledger.data_models.db_models import Client
from payments_ledger.services.ports import AuthRepo


class SqlAlchemyAuthRepo(AuthRepo):
    def __init__(self, session):
        self.session = session

    async def get_client_id_by_api_key_hash(self, api_key_hash: str) -> str | None:
        result = await self.session.execute(
            select(Client).where(Client.api_key_hash == api_key_hash)
        )
        client = result.scalar_one_or_none()
        return str(client.client_id) if client else None
