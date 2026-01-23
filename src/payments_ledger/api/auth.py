import hashlib
from fastapi import Header, HTTPException, Depends
from sqlalchemy import select
from payments_ledger.db.session import get_session
from payments_ledger.data_models.db_models import Client


async def get_client_id(
    authorization: str = Header(...),
    session=Depends(get_session, use_cache=False),
) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    result = await session.execute(select(Client).where(Client.api_key_hash == token_hash))
    client: Client | None = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=401, detail="Invalid api key")

    return str(client.client_id)
