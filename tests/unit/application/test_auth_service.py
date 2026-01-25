import hashlib
import pytest

from payments_ledger.services.auth import authenticate_token, InvalidCredentials


class FakeAuthRepo:
    def __init__(self, mapping):
        self.mapping = mapping

    async def get_client_id_by_api_key_hash(self, api_key_hash: str):
        return self.mapping.get(api_key_hash)


@pytest.mark.asyncio
async def test_authenticate_token_success():
    token = "secret-token"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    repo = FakeAuthRepo({token_hash: "client_1"})

    client_id = await authenticate_token(repo, token)
    assert client_id == "client_1"


@pytest.mark.asyncio
async def test_authenticate_token_invalid():
    repo = FakeAuthRepo({})
    with pytest.raises(InvalidCredentials):
        await authenticate_token(repo, "bad-token")
