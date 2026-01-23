from uuid import uuid4
from payments_ledger.services.idempotency import (
    make_request_hash,
    reserve_idempotency,
    complete_idempotency,
)


async def process_payment(session, client_id, idempotency_key, payload, request_id):
    request_hash = make_request_hash(payload)

    async with session.begin():
        idem_result = await reserve_idempotency(
            session=session,
            client_id=client_id,
            idem_key=idempotency_key,
            request_hash=request_hash,
        )

        if idem_result.state == "duplicate":
            return idem_result.response

        ##payment_process

        response = {
            "payment_id": str(uuid4()),
            "status": "COMPLETED",
            "request_id": request_id,
        }

        idem_result = await complete_idempotency(
            session=session,
            client_id=client_id,
            idem_key=idempotency_key,
            response=response,  ##tpm
        )

        if idem_result.state == "duplicate":
            return idem_result.response

        return response
