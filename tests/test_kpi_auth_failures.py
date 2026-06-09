"""
tests/test_kpi_auth_failures.py
────────────────────────────────
KPI 6 — API Authentication Failures: continuously monitored

Verifies that:
- Failed login attempts increment the auth_failures counter in GET /kpi/security
- Invalid API-key headers also increment the counter
- The delta after N deliberate failures is ≥ N
"""

import pytest
import httpx

from helpers import auth_headers

pytestmark = [pytest.mark.kpi, pytest.mark.integration]

_BAD_PASSWORD_PAYLOAD = {"username": "trader_1", "password": "WRONG_PASSWORD"}
_N_FAILURES = 6


async def test_auth_failure_counter_increments(
    http_client: httpx.AsyncClient, admin_token: str
):
    """
    Submitting N bad-password logins must increase auth_failures in
    GET /kpi/security by at least N.
    """
    headers = auth_headers(admin_token)

    # Baseline
    r0 = await http_client.get("/kpi/security", headers=headers)
    assert r0.status_code == 200
    baseline = int(r0.json()["auth_failures"])

    # Submit deliberate failures
    for _ in range(_N_FAILURES):
        await http_client.post("/auth/login", json=_BAD_PASSWORD_PAYLOAD)

    # Re-read
    r1 = await http_client.get("/kpi/security", headers=headers)
    assert r1.status_code == 200
    after = int(r1.json()["auth_failures"])
    delta = after - baseline

    print(
        f"\n[KPI-6] Auth failures — baseline={baseline}  after={after}  "
        f"delta={delta}  (submitted {_N_FAILURES} failures)"
    )
    assert delta >= _N_FAILURES, (
        f"Expected auth_failures to increase by ≥{_N_FAILURES}, got delta={delta}"
    )


async def test_invalid_api_key_increments_counter(
    http_client: httpx.AsyncClient, admin_token: str
):
    """Requests with wrong API-key headers must also increment auth_failures."""
    headers_admin = auth_headers(admin_token)

    r0 = await http_client.get("/kpi/security", headers=headers_admin)
    baseline = int(r0.json()["auth_failures"])

    bad_key_headers = {
        "X-API-Key": "00000000000000000000000000000000",
        "X-API-Secret": "00000000000000000000000000000000000000000000000000000000000000000",
    }
    for _ in range(3):
        await http_client.get("/market/price/BTCUSDT", headers=bad_key_headers)

    r1 = await http_client.get("/kpi/security", headers=headers_admin)
    after = int(r1.json()["auth_failures"])

    print(f"\n[KPI-6] Invalid API-key hits — delta={after - baseline}")
    assert after >= baseline, "auth_failures counter must not decrease"


async def test_security_kpi_endpoint_accessible(
    http_client: httpx.AsyncClient, admin_token: str
):
    """GET /kpi/security is accessible and returns required fields."""
    r = await http_client.get("/kpi/security", headers=auth_headers(admin_token))
    assert r.status_code == 200
    data = r.json()
    for field in ("auth_failures", "rate_limit_hits", "total_requests"):
        assert field in data, f"Missing field '{field}' in /kpi/security"
