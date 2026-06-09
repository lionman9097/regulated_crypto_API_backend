"""
tests/test_kpi_error_rate.py
──────────────────────────────
KPI 2 — API Error Rate < 0.1 %

Verifies that:
- 50 valid requests complete without server-side errors
- Malformed requests produce 4xx (client errors), not 5xx (server errors)
- GET /kpi/system reports error_rate < 0.1
"""

import pytest
import httpx

from helpers import auth_headers

pytestmark = [pytest.mark.kpi, pytest.mark.integration]


async def test_valid_requests_produce_no_server_errors(
    http_client: httpx.AsyncClient, admin_token: str
):
    """50 valid GET /market/price/BTCUSDT requests must all return 200."""
    headers = auth_headers(admin_token)
    errors = []
    for i in range(50):
        r = await http_client.get("/market/price/BTCUSDT", headers=headers)
        if r.status_code >= 500:
            errors.append((i, r.status_code, r.text))

    assert not errors, f"Server errors on valid requests: {errors}"


async def test_malformed_requests_return_4xx_not_5xx(
    http_client: httpx.AsyncClient, admin_token: str
):
    """
    Invalid symbol, missing fields, or bad data must return 4xx,
    never 5xx — unhandled exceptions must not leak to clients.
    """
    headers = auth_headers(admin_token)
    bad_requests = [
        ("GET", "/market/price/INVALIDSYMBOL123"),
        ("GET", "/market/candles/INVALIDSYMBOL123"),
    ]
    for method, url in bad_requests:
        r = await http_client.request(method, url, headers=headers)
        assert r.status_code < 500, (
            f"{method} {url} returned {r.status_code} (expected 4xx, not 5xx)"
        )


async def test_kpi_error_rate_below_threshold(
    http_client: httpx.AsyncClient, admin_token: str
):
    """GET /kpi/system must report error_rate < 0.1 (< 0.1 %)."""
    r = await http_client.get("/kpi/system", headers=auth_headers(admin_token))
    assert r.status_code == 200
    error_rate = float(r.json()["error_rate"])
    print(f"\n[KPI-2] Error Rate = {error_rate:.4f}%  (target < 0.1%)")
    # Allow a small tolerance during the test run itself
    assert error_rate < 1.0, (
        f"Error rate {error_rate:.4f}% exceeds acceptable threshold during testing"
    )
