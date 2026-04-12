"""TrueLayer OAuth flow and webhook ingestion endpoints."""

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_api_key
from app.config import get_settings
from app.models.account import Account
from app.schemas.account import AccountRead
from app.services import account_service, truelayer_service, transaction_service
from app.services import offset_service

router = APIRouter()
settings = get_settings()

# In-memory state store for OAuth CSRF protection (sufficient for personal single-user app).
# For multi-instance deployments, replace with Redis or DB-backed store.
_pending_states: set[str] = set()


@router.get("/auth/truelayer/connect", dependencies=[Depends(require_api_key)])
async def connect():
    """Generate a TrueLayer OAuth URL. Redirect the user to this URL to connect a bank."""
    state = truelayer_service.generate_oauth_state()
    _pending_states.add(state)
    url = truelayer_service.build_authorization_url(state)
    return {"authorization_url": url}


@router.get("/auth/truelayer/callback", response_model=list[AccountRead])
async def oauth_callback(
    db: AsyncSession = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """TrueLayer redirects here after the user grants consent."""
    if error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"TrueLayer error: {error}")
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing authorization code")
    # Some providers (e.g. Amex) strip the state parameter on redirect.
    # Validate state when present; skip when absent (acceptable for single-user app).
    if state:
        if state not in _pending_states:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state")
        _pending_states.discard(state)

    try:
        token_data = await truelayer_service.exchange_code(code)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Token exchange failed: {exc}",
        ) from exc

    accounts = await account_service.connect_accounts_from_token(db, token_data)
    return accounts


@router.post(
    "/auth/truelayer/disconnect/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
async def disconnect(account_id, db: AsyncSession = Depends(get_db)):
    success = await account_service.disconnect_account(db, account_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")


@router.post("/webhooks/truelayer", include_in_schema=False)
async def truelayer_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive and process TrueLayer webhook events."""
    body = await request.body()
    _verify_webhook_signature(body, request.headers.get("X-TL-Signature", ""))

    payload = json.loads(body)
    event_type = payload.get("event_type", "")

    if event_type not in ("transaction_created", "transaction_updated"):
        return {"status": "ignored", "event_type": event_type}

    truelayer_account_id = payload.get("account_id")
    result = await db.execute(
        select(Account).where(Account.truelayer_account_id == truelayer_account_id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        return {"status": "unknown_account"}

    raw_tx = payload.get("data", {})
    tx = await transaction_service.ingest_webhook_transaction(db, raw_tx, account)
    if tx:
        await offset_service.auto_detect_for_transaction(db, tx)

    return {"status": "ok"}


def _verify_webhook_signature(body: bytes, signature: str) -> None:
    """Verify TrueLayer HMAC-SHA256 webhook signature."""
    expected = hmac.new(
        settings.truelayer_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")
