import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_api_key
from app.schemas.transaction import TransactionFilter, TransactionPatch, TransactionRead
from app.services import transaction_service

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/transactions", response_model=dict)
async def list_transactions(
    account_id: list[uuid.UUID] | None = Query(default=None),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    category: str | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    description: str | None = None,
    include_offsets: bool = False,
    page: int = 1,
    page_size: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
):
    filters = TransactionFilter(
        account_id=account_id,
        from_date=from_date,
        to_date=to_date,
        category=category,
        min_amount=min_amount,
        max_amount=max_amount,
        description=description,
        include_offsets=include_offsets,
        page=page,
        page_size=page_size,
    )
    transactions, total = await transaction_service.query_transactions(db, filters)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [TransactionRead.model_validate(t) for t in transactions],
    }


@router.get("/transactions/{transaction_id}", response_model=TransactionRead)
async def get_transaction(transaction_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.models.transaction import Transaction

    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return tx


@router.patch("/transactions/{transaction_id}", response_model=TransactionRead)
async def patch_transaction(
    transaction_id: uuid.UUID,
    body: TransactionPatch,
    db: AsyncSession = Depends(get_db),
):
    tx = await transaction_service.patch_transaction(
        db, transaction_id, body.merchant_name, body.category
    )
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return tx
