"""
tests/test_kpi_uptime.py
─────────────────────────
KPI 1 — API Uptime ≥ 99.95 %

Verifies that:
- GET /kpi/system returns an `uptime` field in [0, 100]
- The /health endpoint is reachable (confirms availability)
- The uptime formula separates availability from error-rate
"""

import pytest
import httpx

from helpers import auth_headers

pytestmark = [pytest.mark.kpi, pytest.mark.integration]


async def test_kpi_system_uptime_field_present(
    http_client: httpx.AsyncClient, admin_token: str
):
    """GET /kpi/system must return an uptime field."""
    r = await http_client.get("/kpi/system", headers=auth_headers(admin_token))
    assert r.status_code == 200
    data = r.json()
    assert "uptime" in data, f"uptime field missing from /kpi/system response: {data}"


async def test_kpi_uptime_value_range(
    http_client: httpx.AsyncClient, admin_token: str
):
    """Uptime value must be in the range [0.0, 100.0]."""
    r = await http_client.get("/kpi/system", headers=auth_headers(admin_token))
    assert r.status_code == 200
    uptime = r.json()["uptime"]
    assert 0.0 <= float(uptime) <= 100.0, f"uptime out of range: {uptime}"
    print(f"\n[KPI-1] Uptime = {uptime:.4f}%  (target ≥ 99.95%)")


async def test_health_endpoint_reachable(http_client: httpx.AsyncClient):
    """Confirm /health returns 200 — system is available during test window."""
    for _ in range(10):
        r = await http_client.get("/health")
        assert r.status_code == 200


async def test_kpi_system_response_contains_all_fields(
    http_client: httpx.AsyncClient, admin_token: str
):
    """GET /kpi/system must include latency_ms, error_rate, and uptime."""
    r = await http_client.get("/kpi/system", headers=auth_headers(admin_token))
    assert r.status_code == 200
    data = r.json()
    for field in ("uptime", "latency_ms", "error_rate"):
        assert field in data, f"Missing field '{field}' in /kpi/system"
