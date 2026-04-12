"""Chase UK normalizer.

Chase UK is a relatively new bank with standard Open Banking data.
No known quirks beyond TrueLayer defaults — using standard field mapping.
Update once sandbox data is validated.
"""

import uuid
from decimal import Decimal

from app.adapters.base import BankAdapter
from app.adapters.registry import register
from app.models.transaction import TransactionType
from app.schemas.transaction import TransactionCreate


@register
class ChaseAdapter(BankAdapter):
    provider_id = "chase"
    provider_aliases = ("ob-chase",)

    def normalize_transaction(self, raw: dict, account_id: str) -> TransactionCreate:
        amount = Decimal(str(raw["amount"]))
        tx_type = TransactionType.credit if amount >= 0 else TransactionType.debit

        return TransactionCreate(
            account_id=uuid.UUID(account_id),
            truelayer_transaction_id=raw["transaction_id"],
            provider_transaction_id=raw.get("provider_transaction_id"),
            amount=amount,
            currency=raw["currency"],
            description=raw.get("description", ""),
            merchant_name=raw.get("merchant_name") or raw.get("description") or None,
            category=raw.get("transaction_category"),
            timestamp=raw["timestamp"],
            transaction_type=tx_type,
            transaction_classification=raw.get("transaction_classification"),
            running_balance=Decimal(str(raw["running_balance"]["amount"]))
            if raw.get("running_balance")
            else None,
            raw_data=raw,
            is_pending=raw.get("running_balance") is None,
        )
