from payments_ledger.api.schemas import PaymentRequest
from payments_ledger.services.idempotency import make_request_hash


def test_make_request_hash_excludes_request_id():
    req_a = PaymentRequest(
        account_id="acc_1", amount=1000, currency="EUR", direction="DEBIT", request_id="r1"
    )
    req_b = PaymentRequest(
        account_id="acc_1", amount=1000, currency="EUR", direction="DEBIT", request_id="r2"
    )
    assert make_request_hash(req_a.model_dump(exclude_none=True)) == make_request_hash(
        req_b.model_dump(exclude_none=True)
    )
