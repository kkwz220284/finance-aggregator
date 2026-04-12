import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TransactionType(enum.StrEnum):
    debit = "debit"
    credit = "credit"


class OffsetType(enum.StrEnum):
    manual = "manual"
    auto_detected = "auto_detected"


class TransactionOffset(Base, TimestampMixin):
    __tablename__ = "transaction_offsets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debit_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    credit_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    offset_type: Mapped[OffsetType] = mapped_column(Enum(OffsetType), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    debit_transaction: Mapped["Transaction"] = relationship(
        "Transaction", foreign_keys=[debit_transaction_id]
    )
    credit_transaction: Mapped["Transaction"] = relationship(
        "Transaction", foreign_keys=[credit_transaction_id]
    )


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    truelayer_transaction_id: Mapped[str] = mapped_column(String, nullable=False)
    provider_transaction_id: Mapped[str | None] = mapped_column(String, nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    transaction_classification: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    running_balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_pending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Offset link — populated when this transaction is part of an internal transfer
    offset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transaction_offsets.id", ondelete="SET NULL"), nullable=True
    )

    account: Mapped["Account"] = relationship("Account", back_populates="transactions")  # noqa: F821

    __table_args__ = (
        # Enforce uniqueness per account
        Index("uq_transaction_account", "truelayer_transaction_id", "account_id", unique=True),
        # Most common query: transactions for an account ordered by date
        Index("ix_transaction_account_timestamp", "account_id", "timestamp"),
        # Offset detection: find matching amount/currency/date candidates
        Index("ix_transaction_amount_currency_timestamp", "amount", "currency", "timestamp"),
        # Efficient filtering of un-offset transactions
        Index(
            "ix_transaction_no_offset",
            "offset_id",
            postgresql_where="offset_id IS NULL",
        ),
    )
