import re
from fastapi import Header, HTTPException

from payments_ledger.db.session import get_session_factory
from payments_ledger.adapters.db.uow import SqlAlchemyUnitOfWork
from payments_ledger.api.auth import get_client_id_auth
from payments_ledger.adapters.cache.slru_cache import SLRUBalanceCacheL1
from payments_ledger.services.ports import BalanceCacheL1

MIN_IDEM_KEY_LEN = 8
MAX_IDEM_KEY_LEN = 128
IDEM_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]+$")

_balance_cache_l1 = SLRUBalanceCacheL1(capacity=128, protected_ratio=0.8)


def get_balance_cache_l1() -> BalanceCacheL1:
    return _balance_cache_l1


def get_uow():
    return SqlAlchemyUnitOfWork(get_session_factory())


def check_idem_key_format(key: str = Header(..., alias="Idempotency-Key")) -> str:
    key_len = len(key)
    if key_len < MIN_IDEM_KEY_LEN or key_len > MAX_IDEM_KEY_LEN or not IDEM_KEY_RE.fullmatch(key):
        raise HTTPException(status_code=422, detail="INVALID_IDEMPOTENCY_KEY")

    return key


get_client_id = get_client_id_auth
