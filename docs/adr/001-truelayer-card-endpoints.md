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

## Validation

Tested 2026-04-12 with real Amex production credentials:
- 2 cards connected (Amex Rewards, BA Amex Premium)
- 74 transactions synced from BA Amex Premium over 90 days
- Amounts, descriptions, and metadata verified correct
