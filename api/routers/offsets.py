import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_api_key
from app.models.transaction import TransactionOffset
from app.schemas.offset import OffsetCreate, OffsetRead
from app.services import offset_service

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/offsets", response_model=list[OffsetRead])
async def list_offsets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TransactionOffset).order_by(TransactionOffset.created_at.desc())
    )
    return result.scalars().all()


@router.post("/offsets", response_model=OffsetRead, status_code=status.HTTP_201_CREATED)
async def create_offset(body: OffsetCreate, db: AsyncSession = Depends(get_db)):
    try:
        offset = await offset_service.create_manual_offset(
            db, body.debit_transaction_id, body.credit_transaction_id, body.notes
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return offset


@router.delete("/offsets/{offset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offset(offset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    success = await offset_service.delete_offset(db, offset_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offset not found")


@router.post("/offsets/detect", response_model=list[OffsetRead])
async def detect_offsets(
    from_date: datetime,
    to_date: datetime,
    db: AsyncSession = Depends(get_db),
):
    """Run auto-detection across all un-offset credits in the given date range."""
    offsets = await offset_service.detect_offsets_in_range(db, from_date, to_date)
    return offsets
