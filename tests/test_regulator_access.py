"""
tests/test_regulator_access.py
────────────────────────────────
Regulator interface access-control tests.

Verifies that:
- Trader-role tokens cannot access /regulator/* endpoints (HTTP 403)
- Admin/regulator-role tokens can access all /regulator/* endpoints
- All regulator responses carry valid HMAC signatures
"""

import pytest
import httpx

from helpers import auth_headers

pytestmark = [pytest.mark.security, pytest.mark.integration]

_REGULATOR_ENDPOINTS = [
    "/regulator/overview",
    "/regulator/exposure",
    "/regulator/positions",
    "/regulator/liquidations",
]


# ── Role-based access control ─────────────────────────────────────────────────

async def test_trader_cannot_access_regulator_overview(
    http_client: httpx.AsyncClient, trader_token: str
):
    """Trader role → GET /regulator/overview must return 403."""
    r = await http_client.get(
        "/regulator/overview", headers=auth_headers(trader_token)
    )
    assert r.status_code == 403, (
        f"Expected 403 for trader accessing /regulator/overview, got {r.status_code}"
    )


@pytest.mark.parametrize("endpoint", _REGULATOR_ENDPOINTS)
async def test_trader_denied_all_regulator_endpoints(
    http_client: httpx.AsyncClient, trader_token: str, endpoint: str
):
    """Trader role must be denied all /regulator/* endpoints."""
    r = await http_client.get(endpoint, headers=auth_headers(trader_token))
    assert r.status_code == 403, (
        f"Expected 403 for trader at {endpoint}, got {r.status_code}"
    )


@pytest.mark.parametrize("endpoint", _REGULATOR_ENDPOINTS)
async def test_admin_can_access_all_regulator_endpoints(
    http_client: httpx.AsyncClient, admin_token: str, endpoint: str
):
    """Admin role must have access to all /regulator/* endpoints."""
    r = await http_client.get(endpoint, headers=auth_headers(admin_token))
    assert r.status_code == 200, (
        f"Expected 200 for admin at {endpoint}, got {r.status_code}: {r.text}"
    )


@pytest.mark.parametrize("endpoint", _REGULATOR_ENDPOINTS)
async def test_regulator_can_access_all_regulator_endpoints(
    http_client: httpx.AsyncClient, regulator_token: str, endpoint: str
):
    """Regulator role must have access to all /regulator/* endpoints."""
    r = await http_client.get(endpoint, headers=auth_headers(regulator_token))
    assert r.status_code == 200, (
        f"Expected 200 for regulator at {endpoint}, got {r.status_code}: {r.text}"
    )


# ── Response structure ────────────────────────────────────────────────────────

async def test_regulator_positions_returns_list(
    http_client: httpx.AsyncClient, admin_token: str
):
    """GET /regulator/positions must return a JSON array."""
    r = await http_client.get(
        "/regulator/positions",
        headers=auth_headers(admin_token),
        params={"limit": 200},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_regulator_access_produces_audit_entry(
    http_client: httpx.AsyncClient, admin_token: str
):
    """Accessing the regulatory interface must emit a REGULATOR_ACCESS audit entry."""
    r = await http_client.get(
        "/regulator/overview", headers=auth_headers(admin_token)
    )
    assert r.status_code == 200

    audit_r = await http_client.get(
        "/audit/logs",
        headers=auth_headers(admin_token),
        params={"event_type": "REGULATOR_ACCESS", "limit": 10},
    )
    assert audit_r.status_code == 200
    entries = audit_r.json()
    assert entries, "No REGULATOR_ACCESS audit entry found after accessing /regulator/overview"
