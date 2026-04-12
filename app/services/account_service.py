"""Account CRUD and TrueLayer connect/disconnect logic."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.registry import get_adapter
from app.models.account import Account
from app.models.token import TrueLayerToken
from app.schemas.account import AccountCreate
from app.services import truelayer_service
from app.services.crypto import decrypt, encrypt


async def list_accounts(db: AsyncSession) -> list[Account]:
    result = await db.execute(select(Account).where(Account.is_active == True))  # noqa: E712
    return list(result.scalars().all())


async def get_account(db: AsyncSession, account_id: uuid.UUID) -> Account | None:
    result = await db.execute(
        select(Account).where(Account.id == account_id).options(selectinload(Account.token))
    )
    return result.scalar_one_or_none()


async def connect_accounts_from_token(
    db: AsyncSession, token_data: dict
) -> list[Account]:
    """After OAuth callback: fetch TrueLayer accounts, upsert into DB, store tokens."""
    now = datetime.now(UTC)
    access_token = token_data["access_token"]
    raw_accounts = await truelayer_service.get_accounts_and_cards(access_token)

    connected: list[Account] = []
    for raw in raw_accounts:
        provider_id = raw.get("provider", {}).get("provider_id", "unknown")
        adapter = get_adapter(provider_id)
        account_create = adapter.normalize_account(raw)

        # Upsert account
        result = await db.execute(
            select(Account).where(Account.truelayer_account_id == account_create.truelayer_account_id)
        )
        account = result.scalar_one_or_none()
        if account is None:
            account = Account(**account_create.model_dump())
            db.add(account)
            await db.flush()  # get account.id
        else:
            account.display_name = account_create.display_name
            account.is_active = True

        # Upsert token (one per account)
        token_result = await db.execute(
            select(TrueLayerToken).where(TrueLayerToken.account_id == account.id)
        )
        token_row = token_result.scalar_one_or_none()
        if token_row is None:
            token_row = truelayer_service.store_token(token_data, account.id, now)
            db.add(token_row)
        else:
            token_row.access_token_encrypted = encrypt(token_data["access_token"])
            token_row.refresh_token_encrypted = encrypt(token_data["refresh_token"])
            token_row.expires_at = truelayer_service.store_token(token_data, account.id, now).expires_at

        connected.append(account)

    await db.commit()
    return connected


async def disconnect_account(db: AsyncSession, account_id: uuid.UUID) -> bool:
    account = await get_account(db, account_id)
    if account is None:
        return False

    if account.token:
        try:
            access_token = decrypt(account.token.access_token_encrypted)
            await truelayer_service.revoke_token(access_token)
        except Exception:
            pass  # Best-effort revocation
        await db.delete(account.token)

    account.is_active = False
    await db.commit()
    return True
