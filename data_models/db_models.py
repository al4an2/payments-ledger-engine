from sqlalchemy import (
    Column, String, BigInteger, JSON, DateTime, Enum, ForeignKey, UniqueConstraint, Integer
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone
import enum

Base = declarative_base()

# ----------------------
# Client
# ----------------------
class ClientStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"

class Client(Base):
    __tablename__ = "clients"

    client_id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    api_key_hash = Column(String, nullable=False)
    status = Column(Enum(ClientStatus), default=ClientStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

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

    account_id = Column(String, primary_key=True)
    client_id = Column(String, ForeignKey("clients.client_id"), nullable=False)
    ledger_version = Column(BigInteger, nullable=False, default=0)
    balance_type = Column(Enum(BalanceType), nullable=False)
    credit_limit = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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

    entry_id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(String, ForeignKey("accounts.account_id"), nullable=False)
    ledger_version = Column(BigInteger, nullable=False)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String, nullable=False)
    entry_type = Column(Enum(EntryType), nullable=False)
    request_id = Column(String, nullable=False)  # trace to idempotency key / request
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

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

    idempotency_id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String, ForeignKey("clients.client_id"), nullable=False)
    idempotency_key = Column(String, nullable=False)
    request_hash = Column(String, nullable=False)
    response_payload = Column(JSON, nullable=True)
    status = Column(Enum(IdempotencyStatus), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)

    client = relationship("Client", lazy="selectin")
