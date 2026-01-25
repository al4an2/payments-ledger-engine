import hashlib
import pytest

from payments_ledger.adapters.db.auth_repo import SqlAlchemyAuthRepo
from payments_ledger.data_models.db_models import Client


@pytest.mark.asyncio
async def test_sqlalchemy_auth_repo_returns_client_id(db_session):
    token = "secret-token"
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    db_session.add(Client(client_id="client_1", name="Test", api_key_hash=token_hash))
    await db_session.commit()

    repo = SqlAlchemyAuthRepo(db_session)
    client_id = await repo.get_client_id_by_api_key_hash(token_hash)

    assert client_id == "client_1"
