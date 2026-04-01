"""Sync Worker — Cloud Run Job entrypoint.

Reads the SYNC_ACCOUNT_ID environment variable (set by the Cloud Run Job spec
or by the API when triggering a per-account sync). If not set, syncs all active accounts.

Usage:
  SYNC_ACCOUNT_ID=<uuid>  sync a single account
  (no env var)            sync all active accounts
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal, engine
from app.models.account import Account
from app.services import transaction_service


async def sync_one(account: Account) -> int:
    async with AsyncSessionLocal() as db:
        now = datetime.now(UTC)
        count = await transaction_service.sync_account(
            db,
            account,
            from_dt=account.last_synced_at or (now - timedelta(days=90)),
            to_dt=now,
        )
        print(f"[sync] {account.display_name} ({account.provider_id}): {count} transactions upserted")
        return count


async def main() -> None:
    account_id_str = os.environ.get("SYNC_ACCOUNT_ID")

    async with AsyncSessionLocal() as db:
        if account_id_str:
            result = await db.execute(
                select(Account)
                .where(Account.id == uuid.UUID(account_id_str), Account.is_active == True)  # noqa: E712
                .options(selectinload(Account.token))
            )
            accounts = [result.scalar_one()]
        else:
            result = await db.execute(
                select(Account)
                .where(Account.is_active == True)  # noqa: E712
                .options(selectinload(Account.token))
            )
            accounts = list(result.scalars().all())

    if not accounts:
        print("[sync] No active accounts to sync")
        return

    total = 0
    for account in accounts:
        try:
            total += await sync_one(account)
        except Exception as exc:
            print(f"[sync] ERROR syncing {account.display_name}: {exc}")

    print(f"[sync] Done. Total upserted: {total}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
