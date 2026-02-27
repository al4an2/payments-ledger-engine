import hashlib
import pytest

from payments_ledger.adapters.db.auth_repo import SqlAlchemyAuthRepo


@pytest.mark.asyncio
async def test_sqlalchemy_auth_repo_returns_client_id(db_session, seed_client):
    token = "secret-token"
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    await seed_client(db_session, name="Test", api_key_hash=token_hash)

    repo = SqlAlchemyAuthRepo(db_session)
    client_id = await repo.get_client_id_by_api_key_hash(token_hash)

    assert client_id == "client_1"
