import hashlib
from payments_ledger.services.ports import AuthRepo


class InvalidCredentials(Exception):
    code = "INVALID_API_KEY"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def authenticate_token(repo: AuthRepo, token: str) -> str:
    token_hash = _hash_token(token)
    client_id = await repo.get_client_id_by_api_key_hash(token_hash)
    if not client_id:
        raise InvalidCredentials("Invalid api key")
    return client_id
