"""Offset detection and management.

An offset links two transactions that cancel each other out — typically
an internal transfer between the user's own accounts (e.g. Monzo → Chase).
"""

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import OffsetType, Transaction, TransactionOffset

_TRANSFER_KEYWORDS = {"transfer", "move money", "faster payment", "fpd", "internal"}
_DETECTION_WINDOW = timedelta(hours=48)


def _is_likely_transfer(credit_tx: Transaction, debit_tx: Transaction) -> bool:
    """Heuristics to decide if two matching-amount transactions are a transfer."""
    # Check description for transfer keywords
    for tx in (credit_tx, debit_tx):
        desc = (tx.description or "").lower()
        if any(kw in desc for kw in _TRANSFER_KEYWORDS):
            return True

    # Both current accounts — likely a transfer rather than a refund
    # (We'd need account types but those live on Account model; skip for now
    #  and rely on keyword matching. The account type check can be added
    #  once the caller passes account info.)
    return False


async def auto_detect_for_transaction(
    db: AsyncSession, tx: Transaction
) -> TransactionOffset | None:
    """Try to find a matching transfer counterpart for a newly ingested transaction.

    Only runs on credits (positive amounts) — looks for a debit of the same
    absolute amount on a different account within ±48 hours.
    """
    if tx.amount <= 0:
        return None

    window_start = tx.timestamp - _DETECTION_WINDOW
    window_end = tx.timestamp + _DETECTION_WINDOW

    candidates_q = (
        select(Transaction)
        .where(
            Transaction.amount == -tx.amount,
            Transaction.currency == tx.currency,
            Transaction.account_id != tx.account_id,
            Transaction.timestamp.between(window_start, window_end),
            Transaction.offset_id.is_(None),
        )
        .order_by(
            # Closest in time first (approximation — SQLAlchemy doesn't have abs diff ordering
            # easily, so order by timestamp proximity by sorting desc then take first match)
            Transaction.timestamp.desc()
        )
        .limit(5)
    )
    result = await db.execute(candidates_q)
    candidates = result.scalars().all()

    for candidate in candidates:
        if _is_likely_transfer(tx, candidate):
            offset = TransactionOffset(
                debit_transaction_id=candidate.id,
                credit_transaction_id=tx.id,
                amount=tx.amount,
                currency=tx.currency,
                offset_type=OffsetType.auto_detected,
            )
            db.add(offset)
            await db.flush()  # get offset.id

            candidate.offset_id = offset.id
            tx.offset_id = offset.id
            await db.commit()
            return offset

    return None


async def create_manual_offset(
    db: AsyncSession,
    debit_tx_id: uuid.UUID,
    credit_tx_id: uuid.UUID,
    notes: str | None = None,
) -> TransactionOffset:
    """Manually link two transactions as an offset."""
    debit_result = await db.execute(select(Transaction).where(Transaction.id == debit_tx_id))
    credit_result = await db.execute(select(Transaction).where(Transaction.id == credit_tx_id))
    debit_tx = debit_result.scalar_one()
    credit_tx = credit_result.scalar_one()

    offset = TransactionOffset(
        debit_transaction_id=debit_tx.id,
        credit_transaction_id=credit_tx.id,
        amount=abs(debit_tx.amount),
        currency=debit_tx.currency,
        offset_type=OffsetType.manual,
        notes=notes,
    )
    db.add(offset)
    await db.flush()

    debit_tx.offset_id = offset.id
    credit_tx.offset_id = offset.id
    await db.commit()
    return offset


async def delete_offset(db: AsyncSession, offset_id: uuid.UUID) -> bool:
    """Remove an offset and un-link both transactions."""
    result = await db.execute(select(TransactionOffset).where(TransactionOffset.id == offset_id))
    offset = result.scalar_one_or_none()
    if offset is None:
        return False

    # Clear offset_id on both transactions
    for tx_id in (offset.debit_transaction_id, offset.credit_transaction_id):
        tx_result = await db.execute(select(Transaction).where(Transaction.id == tx_id))
        tx = tx_result.scalar_one_or_none()
        if tx:
            tx.offset_id = None

    await db.delete(offset)
    await db.commit()
    return True


async def detect_offsets_in_range(db: AsyncSession, from_dt, to_dt) -> list[TransactionOffset]:
    """Run auto-detection over all un-offset credits in a date range."""
    q = (
        select(Transaction)
        .where(
            Transaction.amount > 0,
            Transaction.offset_id.is_(None),
            Transaction.timestamp.between(from_dt, to_dt),
        )
        .order_by(Transaction.timestamp)
    )
    result = await db.execute(q)
    credits = result.scalars().all()

    found: list[TransactionOffset] = []
    for tx in credits:
        offset = await auto_detect_for_transaction(db, tx)
        if offset:
            found.append(offset)
    return found
