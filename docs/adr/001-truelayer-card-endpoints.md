# ADR-001: TrueLayer Card vs Account Endpoints

**Date:** 2026-04-12
**Status:** Accepted
**Context for:** `app/services/truelayer_service.py`, `app/adapters/`, `api/routers/truelayer.py`

## Context

The initial implementation assumed all TrueLayer providers use the `/data/v1/accounts` endpoint. When connecting a real Amex account in production, we discovered that credit card providers use entirely separate `/data/v1/cards` endpoints.

This is poorly documented by TrueLayer. The failure mode is a `501 Not Implemented` from `/data/v1/accounts` for card-only providers.

## Decisions

### 1. Fetch from both `/accounts` and `/cards`

`get_accounts_and_cards()` calls both endpoints and merges results, tolerating `403`/`501` from either. This means a single OAuth flow works regardless of whether the user connects a bank account, a credit card, or both.

**Alternative considered:** Detect provider type upfront and call the correct endpoint. Rejected because TrueLayer doesn't expose provider type before the data fetch, and a user's consent can span multiple provider types.

### 2. Route transactions by account type

`get_transactions()` and `get_balance()` accept `is_card: bool` to select between `/data/v1/accounts/{id}/transactions` and `/data/v1/cards/{id}/transactions`. The caller checks `account.account_type == AccountType.credit_card`.

### 3. Handle card response shape differences

TrueLayer cards responses use `card_id` and `card_type` instead of `account_id` and `account_type`. The base adapter's `normalize_account()` handles both shapes.

### 4. Provider ID aliases

TrueLayer returns `ob-amex` as the provider ID in production, not `amex`. Rather than rename the adapter, we added a `provider_aliases` mechanism to the registry. The canonical ID stored in the DB remains `amex`.

**Rationale:** Other providers may have similar `ob-` prefixed IDs in production vs sandbox. Aliases let us handle this without duplicating adapters.

### 5. Relaxed OAuth state validation

Some providers (including Amex) strip the `state` parameter from the OAuth callback redirect. The callback now validates state when present but accepts callbacks without it.

**Trade-off:** Reduced CSRF protection. Acceptable for a single-user personal app. For multi-user, consider storing state server-side and matching on the authorization code instead.

### 6. Added `cards` OAuth scope

TrueLayer requires a separate `cards` scope for the `/data/v1/cards` endpoint. Without it, the endpoint returns `403 Forbidden`.

## Consequences

- Bank account providers (Monzo, Chase, NatWest) continue to work via `/data/v1/accounts`
- Credit card providers (Amex) now work via `/data/v1/cards`
- New card providers can be added by registering an adapter with appropriate aliases
- The `is_card` flag threading through `get_transactions`/`get_balance` is a minor code smell but avoids over-engineering

## Verification

### How to verify

From the devcontainer, query the database directly using Python (no `psql` needed):

```bash
# Check connected accounts
uv run python -c "
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def main():
    async with engine.connect() as conn:
        r = await conn.execute(text('SELECT id, provider_id, display_name, account_type, currency, last_synced_at FROM accounts'))
        for row in r: print(row)

asyncio.run(main())
"

# Check transaction counts per account
uv run python -c "
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def main():
    async with engine.connect() as conn:
        r = await conn.execute(text('SELECT a.display_name, count(t.id) FROM accounts a LEFT JOIN transactions t ON t.account_id = a.id GROUP BY a.display_name'))
        for row in r: print(row)

asyncio.run(main())
"

# Check transaction stats
uv run python -c "
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def main():
    async with engine.connect() as conn:
        r = await conn.execute(text('SELECT count(*) as total, min(timestamp) as earliest, max(timestamp) as latest FROM transactions'))
        for row in r: print(row)
        r = await conn.execute(text('SELECT transaction_type, count(*), sum(amount) FROM transactions GROUP BY transaction_type'))
        for row in r: print(row)

asyncio.run(main())
"
```

Or via the API:

```bash
API_KEY="your-api-key"

# List accounts
curl -s -H "X-API-Key: $API_KEY" http://localhost:8080/api/v1/accounts | python -m json.tool

# List transactions (paginated)
curl -s -H "X-API-Key: $API_KEY" "http://localhost:8080/api/v1/transactions?page_size=10" | python -m json.tool

# Sync transactions for an account
curl -s -X POST -H "X-API-Key: $API_KEY" "http://localhost:8080/api/v1/accounts/<account-id>/sync?days=90"
```

### Test results (2026-04-12)

Tested with real Amex production credentials:

| Card | Provider ID (DB) | TrueLayer Provider ID | Transactions | Date Range |
|------|------------------|-----------------------|-------------|------------|
| Amex Rewards Credit | amex | ob-amex | 0 | n/a |
| BA Amex Premium | amex | ob-amex | 74 | 2026-01-13 to 2026-04-09 |

Transaction breakdown:
- 73 debits totalling -3,583.60 GBP
- 1 credit of 1,240.00 GBP (payment)
- Amounts correctly signed (negative for debits)
- Descriptions title-cased from ALL CAPS originals
- Raw TrueLayer data preserved in `raw_data` column
