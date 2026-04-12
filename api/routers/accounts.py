import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_api_key
from app.models.account import Account
from app.schemas.account import AccountRead
from app.services import account_service, transaction_service

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    return await account_service.list_accounts(db)


@router.get("/accounts/{account_id}", response_model=AccountRead)
async def get_account(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    account = await account_service.get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.post("/accounts/{account_id}/sync")
async def sync_account(
    account_id: uuid.UUID,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual transaction sync for this account."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Account).where(Account.id == account_id).options(selectinload(Account.token))
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is not active")

    now = datetime.now(UTC)
    count = await transaction_service.sync_account(
        db, account, from_dt=now - timedelta(days=days), to_dt=now
    )
    return {"synced": count}


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    success = await account_service.disconnect_account(db, account_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
