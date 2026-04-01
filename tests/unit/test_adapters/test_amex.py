"""Unit tests for the Amex adapter normalizer.

These tests are based on assumed TrueLayer field shapes for Amex.
Update once validated against real sandbox data.
"""

import uuid
from decimal import Decimal

from app.adapters.normalizers.amex import AmexAdapter
from app.models.transaction import TransactionType

ACCOUNT_ID = str(uuid.uuid4())

# Assumed shape: amounts positive, transaction_type indicates direction
SAMPLE_DEBIT = {
    "transaction_id": "tx_amex_001",
    "amount": 45.00,
    "currency": "GBP",
    "description": "AMAZON.CO.UK",
    "transaction_type": "DEBIT",
    "timestamp": "2026-03-10T14:00:00Z",
    "transaction_classification": ["shopping"],
}

SAMPLE_PAYMENT_CREDIT = {
    "transaction_id": "tx_amex_pay_001",
    "amount": 600.00,
    "currency": "GBP",
    "description": "PAYMENT RECEIVED THANK YOU",
    "transaction_type": "CREDIT",
    "timestamp": "2026-03-31T08:00:00Z",
    "transaction_classification": [],
}


def test_amex_debit_sign_flipped():
    adapter = AmexAdapter()
    tx = adapter.normalize_transaction(SAMPLE_DEBIT, ACCOUNT_ID)
    assert tx.amount == Decimal("-45.00")
    assert tx.transaction_type == TransactionType.debit


def test_amex_description_title_cased():
    adapter = AmexAdapter()
    tx = adapter.normalize_transaction(SAMPLE_DEBIT, ACCOUNT_ID)
    # "AMAZON.CO.UK" is all upper — should be title-cased
    assert tx.description == "Amazon.Co.Uk"


def test_amex_payment_credit_positive():
    adapter = AmexAdapter()
    tx = adapter.normalize_transaction(SAMPLE_PAYMENT_CREDIT, ACCOUNT_ID)
    assert tx.amount == Decimal("600.00")
    assert tx.transaction_type == TransactionType.credit


def test_amex_no_running_balance():
    adapter = AmexAdapter()
    tx = adapter.normalize_transaction(SAMPLE_DEBIT, ACCOUNT_ID)
    assert tx.running_balance is None
