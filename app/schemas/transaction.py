import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.transaction import TransactionType


class TransactionCreate(BaseModel):
    account_id: uuid.UUID
    truelayer_transaction_id: str
    provider_transaction_id: str | None = None
    amount: Decimal
    currency: str
    description: str
    merchant_name: str | None = None
    category: str | None = None
    timestamp: datetime
    transaction_type: TransactionType
    transaction_classification: list[str] | None = None
    running_balance: Decimal | None = None
    raw_data: dict
    is_pending: bool = False


class TransactionRead(TransactionCreate):
    id: uuid.UUID
    offset_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionPatch(BaseModel):
    merchant_name: str | None = None
    category: str | None = None


class TransactionFilter(BaseModel):
    account_id: list[uuid.UUID] | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    category: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    description: str | None = None
    include_offsets: bool = False
    page: int = 1
    page_size: int = 50


class TransactionSummary(BaseModel):
    category: str | None
    total_amount: Decimal
    transaction_count: int
    period_from: datetime
    period_to: datetime
