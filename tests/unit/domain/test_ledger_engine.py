import pytest

from payments_ledger.ledger_domain.ledger_engine import (
    decide_posting,
    EntryType,
    BalanceType,
    InvalidAmount,
    InsufficientFunds,
    CreditLimitExceeded,
    InvalidAccountConfig,
)


def test_decide_posting_credit_increases_balance():
    result = decide_posting(
        amount=100,
        direction=EntryType.CREDIT,
        current_balance=50,
        balance_type=BalanceType.DEBIT_ONLY,
        credit_limit=None,
        current_ledger_version=7,
    )
    assert result.signed_amount == 100
    assert result.new_balance == 150
    assert result.new_ledger_version == 8
    assert result.entry_type == EntryType.CREDIT


def test_decide_posting_debit_sufficient_debit_only():
    result = decide_posting(
        amount=40,
        direction=EntryType.DEBIT,
        current_balance=100,
        balance_type=BalanceType.DEBIT_ONLY,
        credit_limit=None,
        current_ledger_version=3,
    )
    assert result.signed_amount == -40
    assert result.new_balance == 60
    assert result.entry_type == EntryType.DEBIT


def test_decide_posting_debit_insufficient_debit_only():
    with pytest.raises(InsufficientFunds):
        decide_posting(
            amount=120,
            direction=EntryType.DEBIT,
            current_balance=100,
            balance_type=BalanceType.DEBIT_ONLY,
            credit_limit=None,
            current_ledger_version=1,
        )


def test_decide_posting_credit_allowed_within_limit():
    result = decide_posting(
        amount=300,
        direction=EntryType.DEBIT,
        current_balance=0,
        balance_type=BalanceType.CREDIT_ALLOWED,
        credit_limit=500,
        current_ledger_version=2,
    )
    assert result.new_balance == -300
    assert result.entry_type == EntryType.DEBIT


def test_decide_posting_credit_limit_exceeded():
    with pytest.raises(CreditLimitExceeded):
        decide_posting(
            amount=600,
            direction=EntryType.DEBIT,
            current_balance=0,
            balance_type=BalanceType.CREDIT_ALLOWED,
            credit_limit=500,
            current_ledger_version=2,
        )


def test_decide_posting_invalid_amount():
    with pytest.raises(InvalidAmount):
        decide_posting(
            amount=0,
            direction=EntryType.DEBIT,
            current_balance=100,
            balance_type=BalanceType.DEBIT_ONLY,
            credit_limit=None,
            current_ledger_version=1,
        )


def test_decide_posting_invalid_account_config():
    with pytest.raises(InvalidAccountConfig):
        decide_posting(
            amount=10,
            direction=EntryType.DEBIT,
            current_balance=0,
            balance_type=BalanceType.CREDIT_ALLOWED,
            credit_limit=None,
            current_ledger_version=1,
        )
