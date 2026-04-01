import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.transaction import OffsetType


class OffsetCreate(BaseModel):
    debit_transaction_id: uuid.UUID
    credit_transaction_id: uuid.UUID
    notes: str | None = None


class OffsetRead(BaseModel):
    id: uuid.UUID
    debit_transaction_id: uuid.UUID
    credit_transaction_id: uuid.UUID
    amount: Decimal
    currency: str
    offset_type: OffsetType
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
