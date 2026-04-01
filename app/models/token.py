import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TrueLayerToken(Base, TimestampMixin):
    __tablename__ = "truelayer_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    # Stored Fernet-encrypted; use TrueLayerToken.encrypt/decrypt helpers
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scope: Mapped[str] = mapped_column(String, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="token")  # noqa: F821
