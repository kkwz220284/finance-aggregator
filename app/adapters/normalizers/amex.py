"""Amex normalizer.

Known quirks via TrueLayer (to be validated against sandbox data):
- Amounts may always be positive; transaction_type field indicates direction.
  We flip sign for debits so our schema is consistent (negative = debit).
- Merchant names are often in ALL CAPS — apply .title() for readability.
- Running balance is typically not provided for credit cards.
- Payment credits (bill payment from Monzo etc.) appear as positive entries
  with description containing "PAYMENT" — these are offset candidates.

NOTE: Some of these quirks are assumptions based on TrueLayer documentation.
Validate against real sandbox data and update this normalizer accordingly.
"""

import uuid
from decimal import Decimal

from app.adapters.base import BankAdapter
from app.adapters.registry import register
from app.models.transaction import TransactionType
from app.schemas.transaction import TransactionCreate


@register
class AmexAdapter(BankAdapter):
    provider_id = "amex"
    provider_aliases = ("ob-amex",)

    def normalize_transaction(self, raw: dict, account_id: str) -> TransactionCreate:
        raw_amount = Decimal(str(raw["amount"]))
        tx_type_str = raw.get("transaction_type", "").upper()

        # TrueLayer may report all amounts as positive for Amex;
        # use transaction_type to determine sign
        if tx_type_str == "DEBIT" and raw_amount > 0:
            amount = -raw_amount
            tx_type = TransactionType.debit
        elif tx_type_str == "CREDIT" and raw_amount < 0:
            amount = -raw_amount
            tx_type = TransactionType.credit
        else:
            amount = raw_amount
            tx_type = TransactionType.credit if amount >= 0 else TransactionType.debit

        # Clean up ALL CAPS merchant names
        raw_description = raw.get("description", "")
        description = raw_description.title() if raw_description.isupper() else raw_description

        merchant_name: str | None = None
        if raw.get("merchant_name"):
            mn = raw["merchant_name"]
            merchant_name = mn.title() if mn.isupper() else mn

        return TransactionCreate(
            account_id=uuid.UUID(account_id),
            truelayer_transaction_id=raw["transaction_id"],
            provider_transaction_id=raw.get("provider_transaction_id"),
            amount=amount,
            currency=raw["currency"],
            description=description,
            merchant_name=merchant_name,
            category=raw.get("transaction_category"),
            timestamp=raw["timestamp"],
            transaction_type=tx_type,
            transaction_classification=raw.get("transaction_classification"),
            running_balance=None,  # Amex credit cards don't provide running balance
            raw_data=raw,
            is_pending=raw.get("running_balance") is None,
        )
