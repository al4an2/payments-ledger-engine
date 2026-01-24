from uuid import uuid4
from payments_ledger.services.idempotency import (
    make_request_hash,
    reserve_idempotency,
    complete_idempotency,
)
from payments_ledger.services.ports import UnitOfWork
from payments_ledger.ledger_domain.ledger_engine import (
    AccountNotFound,
    AccountOwnershipError,
    EntryType,
    decide_posting,
)


class InvalidDirection(Exception):
    code = "INVALID_DIRECTION"


def _types_direction(direction: str) -> EntryType:
    try:
        return EntryType(direction)
    except ValueError:
        raise InvalidDirection(f"Unsupported direction: {direction}")


async def process_payment(uow: UnitOfWork, client_id, idempotency_key, payload, request_id):
    request_hash = make_request_hash(payload)

    async with uow:
        idem_result = await reserve_idempotency(
            uow.idempotency_repo,
            client_id,
            idempotency_key,
            request_hash,
        )

        if idem_result.state == "duplicate":
            return idem_result.response

        ##payment_process
        account_lock = await uow.ledger_repo.lock_account(payload.account_id)
        if not account_lock:
            raise AccountNotFound()

        if account_lock.client_id != client_id:
            raise AccountOwnershipError()

        typed_direction = _types_direction(payload.direction)
        current_balance = await uow.ledger_repo.get_balance(
            payload.account_id, payload.currency
        )  # default return 0
        decide_posting(
            amount=payload.amount,
            direction=typed_direction,
            current_balance=current_balance,
            balance_type=account_lock.balance_type,
            credit_limit=account_lock.credit_limit,
            current_ledger_version=account_lock.ledger_version,
        )

        ##payment_process in progress or rollback

        response = {
            "payment_id": str(uuid4()),
            "status": "COMPLETED",
            "request_id": request_id,
        }

        idem_result = await complete_idempotency(
            uow.idempotency_repo,
            client_id,
            idempotency_key,
            response,  ##tpm
        )

        if idem_result.state == "duplicate":
            return idem_result.response

        return response
