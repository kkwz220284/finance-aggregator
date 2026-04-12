"""TrueLayer API client and OAuth token lifecycle management."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx

from app.config import get_settings
from app.models.token import TrueLayerToken
from app.services.crypto import decrypt, encrypt

settings = get_settings()

# Scopes required for full account + transaction access
TRUELAYER_SCOPES = "accounts balance transactions cards offline_access"

# Refresh token proactively if it expires within this window
_REFRESH_BUFFER = timedelta(minutes=5)

# httpx transport with automatic retries on transient errors
_transport = httpx.AsyncHTTPTransport(retries=2)


def build_authorization_url(state: str) -> str:
    base = settings.truelayer_auth_url
    params = {
        "response_type": "code",
        "client_id": settings.truelayer_client_id,
        "redirect_uri": settings.truelayer_redirect_uri,
        "scope": TRUELAYER_SCOPES,
        "state": state,
        # Show all available providers in the TrueLayer consent screen
        "providers": "uk-ob-all uk-oauth-all",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}/?{query}"


async def exchange_code(code: str) -> dict:
    """Exchange an OAuth authorisation code for access + refresh tokens."""
    async with httpx.AsyncClient(transport=_transport, timeout=30) as client:
        resp = await client.post(
            f"{settings.truelayer_auth_url}/connect/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.truelayer_client_id,
                "client_secret": settings.truelayer_client_secret,
                "redirect_uri": settings.truelayer_redirect_uri,
                "code": code,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient(transport=_transport, timeout=30) as client:
        resp = await client.post(
            f"{settings.truelayer_auth_url}/connect/token",
            data={
                "grant_type": "refresh_token",
                "client_id": settings.truelayer_client_id,
                "client_secret": settings.truelayer_client_secret,
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_valid_access_token(token_row: TrueLayerToken, db) -> str:  # type: ignore[type-arg]
    """Return a valid access token, refreshing if necessary. Persists updated token to DB."""
    now = datetime.now(UTC)
    if token_row.expires_at - now > _REFRESH_BUFFER:
        return decrypt(token_row.access_token_encrypted)

    refresh_token = decrypt(token_row.refresh_token_encrypted)
    token_data = await _refresh_access_token(refresh_token)

    token_row.access_token_encrypted = encrypt(token_data["access_token"])
    token_row.refresh_token_encrypted = encrypt(token_data.get("refresh_token", refresh_token))
    token_row.expires_at = now + timedelta(seconds=token_data["expires_in"])
    await db.commit()

    return token_data["access_token"]


async def get_accounts(access_token: str) -> list[dict]:
    async with httpx.AsyncClient(transport=_transport, timeout=30) as client:
        resp = await client.get(
            f"{settings.truelayer_api_url}/data/v1/accounts",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()["results"]


async def get_cards(access_token: str) -> list[dict]:
    """Fetch card accounts (credit cards like Amex) from TrueLayer."""
    async with httpx.AsyncClient(transport=_transport, timeout=30) as client:
        resp = await client.get(
            f"{settings.truelayer_api_url}/data/v1/cards",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()["results"]


async def get_accounts_and_cards(access_token: str) -> list[dict]:
    """Fetch both bank accounts and cards, tolerating 501 from either endpoint."""
    results: list[dict] = []
    for fetcher in (get_accounts, get_cards):
        try:
            results.extend(await fetcher(access_token))
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 501):
                continue
            raise
    return results


async def get_transactions(
    access_token: str,
    truelayer_account_id: str,
    from_dt: datetime,
    to_dt: datetime,
    *,
    is_card: bool = False,
) -> list[dict]:
    resource = "cards" if is_card else "accounts"
    params = {
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    async with httpx.AsyncClient(transport=_transport, timeout=60) as client:
        resp = await client.get(
            f"{settings.truelayer_api_url}/data/v1/{resource}/{truelayer_account_id}/transactions",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        resp.raise_for_status()
        return resp.json()["results"]


async def get_balance(access_token: str, truelayer_account_id: str, *, is_card: bool = False) -> dict:
    resource = "cards" if is_card else "accounts"
    async with httpx.AsyncClient(transport=_transport, timeout=30) as client:
        resp = await client.get(
            f"{settings.truelayer_api_url}/data/v1/{resource}/{truelayer_account_id}/balance",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        results = resp.json()["results"]
        return results[0] if results else {}


async def revoke_token(access_token: str) -> None:
    async with httpx.AsyncClient(transport=_transport, timeout=30) as client:
        await client.post(
            f"{settings.truelayer_auth_url}/connect/revocation",
            data={
                "client_id": settings.truelayer_client_id,
                "client_secret": settings.truelayer_client_secret,
                "token": access_token,
                "token_type_hint": "access_token",
            },
        )


def generate_oauth_state() -> str:
    """Generate a random, unguessable state value for CSRF protection."""
    return secrets.token_urlsafe(32)


def store_token(token_data: dict, account_id: uuid.UUID, now: datetime) -> TrueLayerToken:
    """Build a TrueLayerToken model from a raw token response dict."""
    return TrueLayerToken(
        account_id=account_id,
        access_token_encrypted=encrypt(token_data["access_token"]),
        refresh_token_encrypted=encrypt(token_data["refresh_token"]),
        expires_at=now + timedelta(seconds=token_data["expires_in"]),
        scope=token_data.get("scope", TRUELAYER_SCOPES),
    )
