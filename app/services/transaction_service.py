"""Transaction sync, ingestion, and query logic."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_adapter
from app.models.account import Account
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionFilter
from app.services import truelayer_service


async def sync_account(
    db: AsyncSession,
    account: Account,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> int:
    """Pull transactions from TrueLayer and upsert into DB. Returns count of upserted rows."""
    if not account.token:
        raise ValueError(f"Account {account.id} has no token")

    token_row = account.token
    access_token = await truelayer_service.get_valid_access_token(token_row, db)

    now = datetime.now(UTC)
    to_dt = to_dt or now
    from_dt = from_dt or (account.last_synced_at or (now - timedelta(days=90)))

    from app.models.account import AccountType

    raw_transactions = await truelayer_service.get_transactions(
        access_token,
        account.truelayer_account_id,
        from_dt,
        to_dt,
        is_card=account.account_type == AccountType.credit_card,
    )

    if not raw_transactions:
        return 0

    adapter = get_adapter(account.provider_id)
    normalised = [
        adapter.normalize_transaction(raw, str(account.id)).model_dump() for raw in raw_transactions
    ]

    # Bulk upsert: insert or update on conflict
    stmt = (
        insert(Transaction)
        .values(normalised)
        .on_conflict_do_update(
            index_elements=["truelayer_transaction_id", "account_id"],
            set_={
                "amount": insert(Transaction).excluded.amount,
                "description": insert(Transaction).excluded.description,
                "merchant_name": insert(Transaction).excluded.merchant_name,
                "category": insert(Transaction).excluded.category,
                "is_pending": insert(Transaction).excluded.is_pending,
                "running_balance": insert(Transaction).excluded.running_balance,
                "raw_data": insert(Transaction).excluded.raw_data,
            },
        )
    )
    await db.execute(stmt)

    # Update last_synced_at
    account.last_synced_at = now
    await db.commit()

    return len(normalised)


async def ingest_webhook_transaction(
    db: AsyncSession, raw: dict, account: Account
) -> Transaction | None:
    """Ingest a single transaction from a TrueLayer webhook payload."""
    adapter = get_adapter(account.provider_id)
    tx_data = adapter.normalize_transaction(raw, str(account.id))

    stmt = (
        insert(Transaction)
        .values(tx_data.model_dump())
        .on_conflict_do_update(
            index_elements=["truelayer_transaction_id", "account_id"],
            set_={
                "amount": insert(Transaction).excluded.amount,
                "description": insert(Transaction).excluded.description,
                "merchant_name": insert(Transaction).excluded.merchant_name,
                "is_pending": insert(Transaction).excluded.is_pending,
                "raw_data": insert(Transaction).excluded.raw_data,
            },
        )
        .returning(Transaction)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one_or_none()


async def query_transactions(
    db: AsyncSession, filters: TransactionFilter
) -> tuple[list[Transaction], int]:
    """Returns (transactions, total_count) for the given filters."""
    q = select(Transaction)

    if filters.account_id:
        q = q.where(Transaction.account_id.in_(filters.account_id))
    if filters.from_date:
        q = q.where(Transaction.timestamp >= filters.from_date)
    if filters.to_date:
        q = q.where(Transaction.timestamp <= filters.to_date)
    if filters.category:
        q = q.where(Transaction.category == filters.category)
    if filters.min_amount is not None:
        q = q.where(Transaction.amount >= filters.min_amount)
    if filters.max_amount is not None:
        q = q.where(Transaction.amount <= filters.max_amount)
    if filters.description:
        q = q.where(Transaction.description.ilike(f"%{filters.description}%"))
    if not filters.include_offsets:
        q = q.where(Transaction.offset_id.is_(None))

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    q = (
        q
        .order_by(Transaction.timestamp.desc())
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    )
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def patch_transaction(
    db: AsyncSession, tx_id: uuid.UUID, merchant_name: str | None, category: str | None
) -> Transaction | None:
    result = await db.execute(select(Transaction).where(Transaction.id == tx_id))
    tx = result.scalar_one_or_none()
    if tx is None:
        return None
    if merchant_name is not None:
        tx.merchant_name = merchant_name
    if category is not None:
        tx.category = category
    await db.commit()
    return tx
