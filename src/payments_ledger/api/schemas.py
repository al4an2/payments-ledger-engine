from pydantic import BaseModel, Field
from typing import Literal


class PaymentRequest(BaseModel):
    account_id: str
    amount: int = Field(..., description="minor units, positive")
    currency: str = Field(..., min_length=3, max_length=3)
    direction: Literal["DEBIT", "CREDIT"]
    request_id: str | None = None


class PaymentResponse(BaseModel):
    payment_id: str | None = None
    status: str
    request_id: str
    error_code: str | None = None
    error_message: str | None = None


class BalanceResponse(BaseModel):
    account_id: str
    currency: str
    balance: int | None = None
    status: str
    request_id: str
    error_code: str | None = None
    error_message: str | None = None


class AccountInfoResponse(BaseModel):
    account_id: str
    balance_type: str
    credit_limit: int
    status: str
    request_id: str
    error_code: str | None = None
    error_message: str | None = None
