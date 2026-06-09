"""
tests/test_kpi_liquidation.py
──────────────────────────────
KPI 5 — Liquidation Events < 10 % of open positions

Verifies that:
- GET /regulator/liquidations returns a valid list with required fields
- The liquidation count relative to total positions is below 10 %
- Each liquidation entry contains the mandatory fields defined in Chapter 3
"""

import pytest
import httpx

from helpers import auth_headers

pytestmark = [pytest.mark.kpi, pytest.mark.integration]

_REQUIRED_LIQUIDATION_FIELDS = (
    "id", "symbol", "user_id",
)
_TARGET_LIQUIDATION_PCT = 10.0   # < 10 % of positions


async def test_liquidations_endpoint_accessible(
    http_client: httpx.AsyncClient, admin_token: str
):
    """GET /regulator/liquidations must return 200 and a list."""
    r = await http_client.get(
        "/regulator/liquidations", headers=auth_headers(admin_token)
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_liquidation_entries_have_required_fields(
    http_client: httpx.AsyncClient, admin_token: str
):
    """Each liquidation entry must contain the fields required by Chapter 3."""
    r = await http_client.get(
        "/regulator/liquidations", headers=auth_headers(admin_token)
    )
    assert r.status_code == 200
    entries = r.json()
    if not entries:
        pytest.skip("No liquidation entries recorded yet — skipping field check")

    for entry in entries[:5]:  # check first 5
        for field in _REQUIRED_LIQUIDATION_FIELDS:
            assert field in entry, (
                f"Missing field '{field}' in liquidation entry: {list(entry.keys())}"
            )


async def test_liquidation_rate_below_threshold(
    http_client: httpx.AsyncClient, admin_token: str
):
    """
    KPI 5: liquidations / total_positions must be < 10 %.

    Uses the current position count from GET /regulator/positions and the
    liquidation count from GET /regulator/liquidations.
    """
    liq_r = await http_client.get(
        "/regulator/liquidations", headers=auth_headers(admin_token)
    )
    assert liq_r.status_code == 200
    liquidation_count = len(liq_r.json())

    pos_r = await http_client.get(
        "/regulator/positions",
        headers=auth_headers(admin_token),
        params={"limit": 1000},
    )
    assert pos_r.status_code == 200
    total_positions = len(pos_r.json())

    if total_positions == 0:
        print("\n[KPI-5] No positions recorded — liquidation rate = N/A")
        pytest.skip("No positions recorded yet")

    liquidation_pct = (liquidation_count / total_positions) * 100.0
    print(
        f"\n[KPI-5] Liquidations={liquidation_count}  "
        f"TotalPositions={total_positions}  "
        f"Rate={liquidation_pct:.2f}%  (target < {_TARGET_LIQUIDATION_PCT}%)"
    )
    assert liquidation_pct < _TARGET_LIQUIDATION_PCT, (
        f"Liquidation rate {liquidation_pct:.2f}% exceeds {_TARGET_LIQUIDATION_PCT}% target"
    )
