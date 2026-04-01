import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.account import AccountType


class AccountBase(BaseModel):
    truelayer_account_id: str
    provider_id: str
    display_name: str
    account_type: AccountType
    currency: str
    iban: str | None = None


class AccountCreate(AccountBase):
    pass


class AccountRead(AccountBase):
    id: uuid.UUID
    is_active: bool
    last_synced_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
