"""Monzo normalizer.

Monzo via TrueLayer exposes extra fields in the `meta` object:
- meta.merchant.name       — cleaned merchant name
- meta.category            — Monzo's own category (eating_out, transport, etc.)
- meta.notes               — user-added notes on the transaction
- meta.is_topup            — true for incoming top-ups

Amounts follow TrueLayer convention: negative = debit, positive = credit.
"""

import uuid
from decimal import Decimal

from app.adapters.base import BankAdapter
from app.adapters.registry import register
from app.models.transaction import TransactionType
from app.schemas.transaction import TransactionCreate

# Monzo category → normalised category
_MONZO_CATEGORY_MAP = {
    "eating_out": "eating_out",
    "groceries": "groceries",
    "transport": "transport",
    "entertainment": "entertainment",
    "shopping": "shopping",
    "bills": "bills",
    "cash": "cash",
    "holidays": "travel",
    "health": "health",
    "personal_care": "personal_care",
    "family": "family",
    "finances": "finances",
    "general": "general",
}


@register
class MonzoAdapter(BankAdapter):
    provider_id = "monzo"
    provider_aliases = ("ob-monzo",)

    def normalize_transaction(self, raw: dict, account_id: str) -> TransactionCreate:
        meta = raw.get("meta", {})
        merchant = meta.get("merchant") or {}

        amount = Decimal(str(raw["amount"]))
        tx_type = TransactionType.credit if amount >= 0 else TransactionType.debit

        merchant_name = merchant.get("name") or raw.get("description") or ""
        monzo_category = meta.get("category", "")
        category = _MONZO_CATEGORY_MAP.get(monzo_category, monzo_category or None)

        return TransactionCreate(
            account_id=uuid.UUID(account_id),
            truelayer_transaction_id=raw["transaction_id"],
            provider_transaction_id=meta.get("provider_id"),
            amount=amount,
            currency=raw["currency"],
            description=raw.get("description", ""),
            merchant_name=merchant_name or None,
            category=category,
            timestamp=raw["timestamp"],
            transaction_type=tx_type,
            transaction_classification=raw.get("transaction_classification"),
            running_balance=Decimal(str(raw["running_balance"]["amount"])) if raw.get("running_balance") else None,
            raw_data=raw,
            is_pending=raw.get("running_balance") is None,
        )
