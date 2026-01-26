import json
import hashlib
from typing import Mapping, Any

from payments_ledger.services.ports import IdempotencyRepo, IdemResult, IdempotencyState


async def reserve_idempotency(
    repo: IdempotencyRepo, client_id, idem_key, request_hash
) -> IdemResult:
    return await repo.reserve(client_id, idem_key, request_hash)


async def complete_idempotency(
    repo: IdempotencyRepo,
    client_id,
    idem_key,
    response,
    status: IdempotencyState = IdempotencyState.COMPLETED,
) -> IdemResult:
    return await repo.complete(client_id, idem_key, response)


def make_request_hash(payload: Mapping[str, Any]) -> str:
    body = dict(payload)
    body.pop("request_id", None)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
