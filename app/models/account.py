import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AccountType(str, enum.Enum):
    current = "current"
    savings = "savings"
    credit_card = "credit_card"


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    truelayer_account_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    provider_id: Mapped[str] = mapped_column(String, nullable=False)  # monzo | chase | amex | natwest
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    iban: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )
    token: Mapped["TrueLayerToken | None"] = relationship(  # noqa: F821
        "TrueLayerToken", back_populates="account", uselist=False, cascade="all, delete-orphan"
    )
