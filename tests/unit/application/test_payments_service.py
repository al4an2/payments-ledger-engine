import pytest

from payments_ledger.services.payments import _types_direction, InvalidDirection
from payments_ledger.ledger_domain.ledger_engine import EntryType


def test_types_direction_valid():
    assert _types_direction("DEBIT") == EntryType.DEBIT
    assert _types_direction("CREDIT") == EntryType.CREDIT


def test_types_direction_invalid():
    with pytest.raises(InvalidDirection):
        _types_direction("REFUND")
