from fastapi import Header, HTTPException, Depends
from payments_ledger.db.session import get_session
from payments_ledger.adapters.db.auth_repo import SqlAlchemyAuthRepo
from payments_ledger.services.auth import authenticate_token, InvalidCredentials


async def get_client_id_auth(
    authorization: str = Header(...),
    session=Depends(get_session, use_cache=False),
) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    repo = SqlAlchemyAuthRepo(session)

    try:
        return await authenticate_token(repo, token)
    except InvalidCredentials as exc:
        raise HTTPException(status_code=401, detail=exc.code)
