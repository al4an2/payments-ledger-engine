from src.payments_ledger.services.idempotency import make_request_hash


async def process_payment(session, client_id, idempotency_key, payload):
    request_hash = make_request_hash(payload)