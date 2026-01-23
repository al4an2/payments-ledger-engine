from sqlalchemy import (
    String,
    BigInteger,
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
    Integer,
    text,
)
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
import enum
from datetime import datetime
from typing import Any


class Base(DeclarativeBase):
    pass


# ----------------------
# Client
# ----------------------
class ClientStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class Client(Base):
    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=True)
    api_key_hash: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[ClientStatus] = mapped_column(Enum(ClientStatus), default=ClientStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Optional relationship; lazy="selectin" avoids N+1
    accounts = relationship("Account", back_populates="client", lazy="selectin")


# ----------------------
# Account
# ----------------------
class BalanceType(enum.Enum):
    DEBIT_ONLY = "DEBIT_ONLY"
    CREDIT_ALLOWED = "CREDIT_ALLOWED"


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.client_id"), nullable=False)
    ledger_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    balance_type: Mapped[BalanceType] = mapped_column(Enum(BalanceType), nullable=False)
    credit_limit: Mapped[int] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    client = relationship("Client", back_populates="accounts", lazy="selectin")
    ledger_entries = relationship("LedgerEntry", back_populates="account", lazy="selectin")


# ----------------------
# Ledger Entries
# ----------------------
class EntryType(enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (UniqueConstraint("account_id", "ledger_version"),)

    entry_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.account_id"), nullable=False
    )
    ledger_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    entry_type: Mapped[EntryType] = mapped_column(Enum(EntryType), nullable=False)
    request_id: Mapped[str] = mapped_column(
        String, nullable=False
    )  # trace to idempotency key / request
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    account = relationship("Account", back_populates="ledger_entries", lazy="selectin")


# ----------------------
# Idempotency Keys
# ----------------------
class IdempotencyStatus(enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("client_id", "idempotency_key"),)

    idempotency_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.client_id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    request_hash: Mapped[str] = mapped_column(String, nullable=False)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[IdempotencyStatus] = mapped_column(Enum(IdempotencyStatus), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    client = relationship("Client", lazy="selectin")
