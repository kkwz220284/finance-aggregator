"""
Validate the Amex normalizer against real TrueLayer sandbox data.

Usage (from project root, with the full stack running):
    uv run python scripts/test_amex_sandbox.py

Steps:
  1. Calls /auth/truelayer/connect to get an OAuth URL.
  2. You open the URL in a browser, select Amex in the TrueLayer sandbox,
     and log in with the sandbox credentials (usually user: john, pass: doe).
  3. TrueLayer redirects to localhost:8080/api/v1/auth/truelayer/callback.
  4. This script polls until an Amex account appears in the DB.
  5. Fetches raw transactions from TrueLayer sandbox.
  6. Runs each through the AmexAdapter normalizer.
  7. Prints raw vs normalised output side-by-side so you can verify the
     normalizer's assumptions and update it if needed.
"""

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

API_BASE = "http://localhost:8080/api/v1"
API_KEY = None  # loaded from .env below

POLL_INTERVAL = 3  # seconds
POLL_TIMEOUT = 120  # seconds


def load_api_key() -> str:
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line.startswith("API_KEY="):
                return line.split("=", 1)[1]
    raise RuntimeError("API_KEY not found in .env")


async def get_connect_url(client: httpx.AsyncClient) -> str:
    resp = await client.get(f"{API_BASE}/auth/truelayer/connect")
    resp.raise_for_status()
    return resp.json()["authorization_url"]


async def poll_for_amex_account(client: httpx.AsyncClient) -> dict:
    """Poll the accounts endpoint until an Amex account appears."""
    deadline = asyncio.get_event_loop().time() + POLL_TIMEOUT
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"{API_BASE}/accounts")
        if resp.status_code == 200:
            accounts = resp.json()
            amex = [a for a in accounts if "amex" in a.get("provider_id", "").lower()]
            if amex:
                return amex[0]
        await asyncio.sleep(POLL_INTERVAL)
    raise TimeoutError(f"No Amex account appeared within {POLL_TIMEOUT}s after completing OAuth.")


async def fetch_raw_transactions(access_token: str, truelayer_account_id: str) -> list[dict]:
    """Fetch raw transactions directly from TrueLayer sandbox."""
    to_dt = datetime.now(UTC)
    from_dt = to_dt - timedelta(days=90)
    params = {
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    async with httpx.AsyncClient(timeout=30) as tl_client:
        resp = await tl_client.get(
            f"https://api.truelayer-sandbox.com/data/v1/accounts/{truelayer_account_id}/transactions",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])


def print_comparison(raw: dict, normalised) -> None:
    print("\n" + "=" * 70)
    print("RAW from TrueLayer:")
    print(json.dumps(raw, indent=2, default=str))
    print("\nNORMALISED:")
    d = normalised.model_dump()
    for k, v in d.items():
        if isinstance(v, Decimal):
            d[k] = float(v)
    print(json.dumps(d, indent=2, default=str))


async def main() -> None:
    # Import here so the script can be run from project root without install
    sys.path.insert(0, ".")
    from app.adapters.normalizers.amex import AmexAdapter

    api_key = load_api_key()
    headers = {"X-API-Key": api_key}

    async with httpx.AsyncClient(base_url=API_BASE, headers=headers, timeout=10) as client:
        # Step 1: get OAuth URL
        try:
            url = await get_connect_url(client)
        except httpx.ConnectError:
            print("ERROR: Cannot reach the API at localhost:8080.")
            print("Start the stack first:  docker compose up -d")
            sys.exit(1)

        print("\n" + "=" * 70)
        print("Open this URL in your browser to connect Amex via TrueLayer sandbox:")
        print(f"\n  {url}\n")
        print("Sandbox login: user=john  password=doe  (select Amex as the provider)")
        print("=" * 70)
        print(f"\nWaiting up to {POLL_TIMEOUT}s for the OAuth callback to complete...")

        # Step 2: wait for account
        try:
            account = await poll_for_amex_account(client)
        except TimeoutError as e:
            print(f"\nERROR: {e}")
            sys.exit(1)

        print(f"\nAmex account found: {account['id']} ({account.get('display_name', '')})")

        # Step 3: get a fresh access token from the DB
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.db.session import AsyncSessionLocal
        from app.models.account import Account
        from app.services.truelayer_service import get_valid_access_token

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Account)
                .where(Account.id == account["id"])
                .options(selectinload(Account.token))
            )
            acc = result.scalar_one_or_none()
            if acc is None or acc.token is None:
                print("ERROR: Account has no stored token.")
                sys.exit(1)

            access_token = await get_valid_access_token(acc.token, db)
            truelayer_account_id = acc.truelayer_account_id

    # Step 4: fetch raw transactions from TrueLayer
    print("\nFetching raw transactions from TrueLayer sandbox...")
    raw_txs = await fetch_raw_transactions(access_token, truelayer_account_id)
    print(f"Got {len(raw_txs)} transaction(s).")

    if not raw_txs:
        print("No transactions returned. The sandbox may not have data for this account.")
        return

    # Step 5: run through normalizer and compare
    adapter = AmexAdapter()
    errors = []
    for raw in raw_txs:
        try:
            normalised = adapter.normalize_transaction(raw, account["id"])
            print_comparison(raw, normalised)
        except Exception as exc:
            errors.append((raw.get("transaction_id"), exc))
            print(f"\nERROR normalising {raw.get('transaction_id')}: {exc}")
            print("RAW:", json.dumps(raw, indent=2, default=str))

    print("\n" + "=" * 70)
    print(
        f"Done. {len(raw_txs) - len(errors)}/{len(raw_txs)} transactions normalised successfully."
    )
    if errors:
        print(f"{len(errors)} error(s) — see above. Update the AmexAdapter normalizer accordingly.")


if __name__ == "__main__":
    asyncio.run(main())
