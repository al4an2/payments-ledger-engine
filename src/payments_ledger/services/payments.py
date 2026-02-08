import os
from uuid import uuid4
from payments_ledger.services.idempotency import (
    make_request_hash,
    reserve_idempotency,
    complete_idempotency,
)
from payments_ledger.services.ports import (
    UnitOfWork,
    IdempotencyState,
    PaymentResult,
    BalanceResult,
    BalanceStatus,
)
from payments_ledger.ledger_domain.ledger_engine import (
    AccountNotFound,
    AccountOwnershipError,
    EntryType,
    InvalidAmount,
    InsufficientFunds,
    CreditLimitExceeded,
    InvalidAccountConfig,
    decide_posting,
)

DEBUG_ERRORS = os.getenv("PAYMENTS_DEBUG_ERRORS", "0") == "1"


class InvalidDirection(Exception):
    code = "INVALID_DIRECTION"


def _error_response(exc: Exception, request_id: str) -> PaymentResult:
    return PaymentResult(
        payment_id=None,
        status=IdempotencyState.FAILED,
        request_id=request_id,
        error_code=getattr(exc, "code", "UNKNOWN_ERROR"),
        error_message=str(exc) if DEBUG_ERRORS else None,
    )


def _types_direction(direction: str) -> EntryType:
    try:
        return EntryType(direction)
    except ValueError:
        raise InvalidDirection(f"Unsupported direction: {direction}")


async def process_payment(uow: UnitOfWork, client_id, idempotency_key, payload, request_id):
    request_hash = make_request_hash(
        {
            "account_id": payload.account_id,
            "amount": payload.amount,
            "currency": payload.currency,
            "direction": payload.direction,
        }
    )

    async with uow:
        try:
            idem_result = await reserve_idempotency(
                uow.idempotency_repo,
                client_id,
                idempotency_key,
                request_hash,
            )

            if idem_result.state == "duplicate":
                return idem_result.response

            ##payment_process start
            account_lock = await uow.ledger_repo.lock_account_for_client(
                payload.account_id, client_id
            )
            if not account_lock:
                raise AccountNotFound()

            current_balance = await uow.ledger_repo.get_balance(
                payload.account_id, payload.currency
            )  # default return 0

            typed_direction = _types_direction(payload.direction)
            decision = decide_posting(
                amount=payload.amount,
                direction=typed_direction,
                current_balance=current_balance,
                balance_type=account_lock.balance_type,
                credit_limit=account_lock.credit_limit,
                current_ledger_version=account_lock.ledger_version,
            )

            await uow.ledger_repo.insert_entry(
                account_id=payload.account_id,
                ledger_version=decision.new_ledger_version,
                amount=decision.signed_amount,
                currency=payload.currency,
                entry_type=decision.entry_type,
                request_id=request_id,
            )

            await uow.ledger_repo.update_account_version(
                account_id=payload.account_id, ledger_version=decision.new_ledger_version
            )

            response = PaymentResult(
                payment_id=str(uuid4()),
                status=IdempotencyState.COMPLETED,
                request_id=request_id,
            )
        except (
            InvalidDirection,
            InvalidAmount,
            InsufficientFunds,
            CreditLimitExceeded,
            InvalidAccountConfig,
            AccountNotFound,
            AccountOwnershipError,
        ) as exc:
            response = _error_response(exc, request_id)

        payload = response.to_dict()
        idem_result = await complete_idempotency(
            uow.idempotency_repo, client_id, idempotency_key, payload, response.status
        )

        if idem_result.state == "duplicate":
            return idem_result.response

        return payload


async def balance_process(uow: UnitOfWork, client_id, payload, request_id):
    async with uow:
        try:
            account_data = await uow.ledger_repo.get_account_for_client(
                payload.account_id, client_id
            )

            if not account_data:
                raise AccountNotFound()

            balance_result = await uow.ledger_repo.get_balance(
                payload.account_id, payload.currency
            )  # default return 0

            result = BalanceResult(
                account_id=payload.account_id,
                currency=payload.currency,
                request_id=request_id,
                balance=balance_result,
                status=BalanceStatus.OK,
            )
        except (AccountNotFound, AccountOwnershipError) as exc:
            result = BalanceResult(
                account_id=payload.account_id,
                currency=payload.currency,
                request_id=request_id,
                balance=None,
                status=BalanceStatus.FAILED,
                error_code=getattr(exc, "code", "UNKNOWN_ERROR"),
                error_message=str(exc) if DEBUG_ERRORS else None,
            )

    return result.to_dict()
