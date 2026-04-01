from abc import ABC, abstractmethod
from typing import ClassVar

from app.schemas.account import AccountCreate
from app.schemas.transaction import TransactionCreate


class BankAdapter(ABC):
    provider_id: ClassVar[str]

    @abstractmethod
    def normalize_transaction(self, raw: dict, account_id: str) -> TransactionCreate:
        """Map a raw TrueLayer transaction dict to the common schema."""
        ...

    def normalize_account(self, raw: dict) -> AccountCreate:
        """Default implementation using standard TrueLayer fields.
        Banks with non-standard fields should override this."""
        from app.models.account import AccountType

        account_type_map = {
            "TRANSACTION": AccountType.current,
            "SAVINGS": AccountType.savings,
            "CREDIT_CARD": AccountType.credit_card,
        }
        return AccountCreate(
            truelayer_account_id=raw["account_id"],
            provider_id=self.provider_id,
            display_name=raw["display_name"],
            account_type=account_type_map.get(raw.get("account_type", ""), AccountType.current),
            currency=raw["currency"],
            iban=raw.get("account_number", {}).get("iban"),
        )
