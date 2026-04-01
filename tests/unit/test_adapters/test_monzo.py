"""Unit tests for the Monzo adapter normalizer."""

import uuid
from decimal import Decimal

from app.adapters.normalizers.monzo import MonzoAdapter
from app.models.transaction import TransactionType

ACCOUNT_ID = str(uuid.uuid4())

SAMPLE_DEBIT = {
    "transaction_id": "tx_monzo_001",
    "amount": -12.50,
    "currency": "GBP",
    "description": "TESCO STORES",
    "timestamp": "2026-03-15T10:30:00Z",
    "transaction_classification": ["groceries"],
    "running_balance": {"amount": 487.50, "currency": "GBP"},
    "meta": {
        "merchant": {"name": "Tesco"},
        "category": "groceries",
    },
}

SAMPLE_CREDIT = {
    "transaction_id": "tx_monzo_002",
    "amount": 1000.00,
    "currency": "GBP",
    "description": "Faster Payment",
    "timestamp": "2026-03-15T09:00:00Z",
    "transaction_classification": [],
    "running_balance": {"amount": 1000.00, "currency": "GBP"},
    "meta": {"category": "finances"},
}


def test_monzo_debit_amount_is_negative():
    adapter = MonzoAdapter()
    tx = adapter.normalize_transaction(SAMPLE_DEBIT, ACCOUNT_ID)
    assert tx.amount == Decimal("-12.50")
    assert tx.transaction_type == TransactionType.debit


def test_monzo_merchant_name_from_meta():
    adapter = MonzoAdapter()
    tx = adapter.normalize_transaction(SAMPLE_DEBIT, ACCOUNT_ID)
    assert tx.merchant_name == "Tesco"


def test_monzo_category_mapped():
    adapter = MonzoAdapter()
    tx = adapter.normalize_transaction(SAMPLE_DEBIT, ACCOUNT_ID)
    assert tx.category == "groceries"


def test_monzo_credit_is_positive():
    adapter = MonzoAdapter()
    tx = adapter.normalize_transaction(SAMPLE_CREDIT, ACCOUNT_ID)
    assert tx.amount == Decimal("1000.00")
    assert tx.transaction_type == TransactionType.credit


def test_monzo_truelayer_id_preserved():
    adapter = MonzoAdapter()
    tx = adapter.normalize_transaction(SAMPLE_DEBIT, ACCOUNT_ID)
    assert tx.truelayer_transaction_id == "tx_monzo_001"
