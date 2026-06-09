"""
tests/test_auth_security.py
────────────────────────────
Security tests: JWT expiry, scope enforcement, deactivated keys.

These tests exercise the API Gateway policy-enforcement layer described in
Chapter 3 (Section 3.4) and verify the scope-enforcement results already
presented in the existing bab4.tex Section 2.

Note: the rate-limiting test lives in test_zzz_rate_limit.py so it runs
last in the suite and does not poison downstream tests.
"""

import asyncio

import pytest
import httpx

from helpers import auth_headers, api_key_headers

pytestmark = [pytest.mark.security, pytest.mark.integration]


# ── JWT validity ──────────────────────────────────────────────────────────────

async def test_invalid_jwt_returns_401(http_client: httpx.AsyncClient):
    """A structurally invalid JWT must be rejected with 401."""
    r = await http_client.get(
        "/market/price/BTCUSDT",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert r.status_code == 401


async def test_expired_jwt_returns_401(http_client: httpx.AsyncClient):
    """
    A well-formed but expired JWT must return 401.
    We forge an expired token using the test JWT secret.
    """
    import time
    import os
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

    from core.security import create_access_token
    from unittest.mock import patch

    # Create a token with a negative expiry to simulate expiry
    with patch("core.security.settings") as mock_settings:
        mock_settings.jwt_secret_key = os.environ.get("JWT_SECRET_KEY", "test-jwt-secret-key")
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expire_minutes = -1   # already expired
        expired_token = create_access_token(subject="1", extra_claims={"role": "trader"})

    r = await http_client.get(
        "/market/price/BTCUSDT",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert r.status_code == 401, f"Expected 401 for expired JWT, got {r.status_code}"


# ── Scope enforcement ─────────────────────────────────────────────────────────

async def test_readonly_key_cannot_place_orders(
    http_client: httpx.AsyncClient,
    readonly_api_key,
    trader_token: str,
    trader_user_id: int,
):
    """
    An API key with only read:market scope must receive 403 when attempting
    POST /orders (which requires write:orders).
    """
    key_id, secret = readonly_api_key

    price_r = await http_client.get(
        "/market/price/BTCUSDT", headers=auth_headers(trader_token)
    )
    current_price = float(price_r.json()["price"])

    r = await http_client.post(
        "/orders",
        json={
            "user_id": trader_user_id,
            "symbol": "BTCUSDT",
            "side": "buy",
            "size": 0.001,
            "leverage": 5,
            "order_type": "limit",
            "limit_price": round(current_price * 0.5, 1),
        },
        headers=api_key_headers(key_id, secret),
    )
    assert r.status_code == 403, (
        f"Expected 403 for read-only key posting an order, got {r.status_code}: {r.text}"
    )


async def test_readonly_key_can_read_market(
    http_client: httpx.AsyncClient,
    readonly_api_key,
):
    """API key with read:market scope must be able to GET /market/price."""
    key_id, secret = readonly_api_key
    r = await http_client.get(
        "/market/price/BTCUSDT",
        headers=api_key_headers(key_id, secret),
    )
    assert r.status_code == 200


async def test_full_key_can_place_orders(
    http_client: httpx.AsyncClient,
    api_key_pair,
    trader_token: str,
    trader_user_id: int,
    placed_orders: list,
):
    """API key with write:orders scope must be able to POST /orders."""
    key_id, secret = api_key_pair

    price_r = await http_client.get(
        "/market/price/BTCUSDT", headers=auth_headers(trader_token)
    )
    current_price = float(price_r.json()["price"])

    r = await http_client.post(
        "/orders",
        json={
            "user_id": trader_user_id,
            "symbol": "BTCUSDT",
            "side": "buy",
            "size": 0.002,
            "leverage": 5,
            "order_type": "limit",
            "limit_price": round(current_price * 0.5, 1),
        },
        headers=api_key_headers(key_id, secret),
    )
    if r.status_code == 400 and "balance" in r.text.lower():
        pytest.skip("Insufficient balance — run tests/seed_test_data.py first")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    placed_orders.append(r.json()["order"]["order_id"])


# ── Deactivated key ───────────────────────────────────────────────────────────

async def test_deactivated_key_returns_401(
    http_client: httpx.AsyncClient, trader_token: str
):
    """A deactivated API key must return 401 on any authenticated request."""
    headers = auth_headers(trader_token)

    # Create and immediately deactivate
    create_r = await http_client.post(
        "/api-keys",
        json={"label": "deactivation-test", "scopes": ["read:market"]},
        headers=headers,
    )
    assert create_r.status_code == 201
    key_id = create_r.json()["key_id"]
    secret = create_r.json()["secret"]

    del_r = await http_client.delete(f"/api-keys/{key_id}", headers=headers)
    assert del_r.status_code == 204

    r = await http_client.get(
        "/market/price/BTCUSDT",
        headers=api_key_headers(key_id, secret),
    )
    assert r.status_code == 401, (
        f"Deactivated key should return 401, got {r.status_code}"
    )
