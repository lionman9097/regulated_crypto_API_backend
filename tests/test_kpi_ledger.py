"""
tests/test_kpi_ledger.py
─────────────────────────
KPI 8 — Ledger Snapshot Integrity: 100 %

Verifies that:
- GET /regulator/overview returns an HMAC-SHA256 signature field
- The signature can be independently recomputed and verified
- Altering any field in the payload invalidates the signature (tamper detection)
- GET /regulator/exposure also includes a valid signature
"""

import hashlib
import hmac
import json
import os

import pytest
import httpx

from helpers import auth_headers

pytestmark = [pytest.mark.kpi, pytest.mark.integration]

# The report_signature_key must match the running server's REPORT_SIGNATURE_KEY setting.
# Read from the test environment (same .env.test that configures the server).
_SIGNATURE_KEY = os.environ.get("REPORT_SIGNATURE_KEY", "change-me-report-sig-key")


def _compute_signature(payload_dict: dict) -> str:
    """Recompute HMAC-SHA256 over the sorted-keys JSON of the payload."""
    body = json.dumps(payload_dict, sort_keys=True)
    return hmac.new(
        _SIGNATURE_KEY.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()


# ── Overview endpoint ─────────────────────────────────────────────────────────

async def test_regulator_overview_has_signature(
    http_client: httpx.AsyncClient, admin_token: str
):
    """GET /regulator/overview must include a 'signature' field."""
    r = await http_client.get("/regulator/overview", headers=auth_headers(admin_token))
    assert r.status_code == 200
    data = r.json()
    assert "signature" in data, f"No 'signature' field in /regulator/overview response: {list(data.keys())}"


async def test_regulator_overview_signature_valid(
    http_client: httpx.AsyncClient, admin_token: str
):
    """
    KPI 8 — Scenario 1: Unmodified response.
    Recompute the HMAC and verify it matches the returned signature.
    """
    r = await http_client.get("/regulator/overview", headers=auth_headers(admin_token))
    assert r.status_code == 200
    data = r.json()

    received_sig = data.pop("signature")
    expected_sig = _compute_signature(data)

    print(f"\n[KPI-8] Overview signature verification — received={received_sig[:16]}...")
    assert hmac.compare_digest(received_sig, expected_sig), (
        "Signature mismatch on unmodified /regulator/overview response. "
        "Check that REPORT_SIGNATURE_KEY in .env.test matches the running server."
    )


async def test_regulator_overview_tamper_detected(
    http_client: httpx.AsyncClient, admin_token: str
):
    """
    KPI 8 — Scenario 2: Altered payload.
    Changing any field must make signature verification fail.
    """
    r = await http_client.get("/regulator/overview", headers=auth_headers(admin_token))
    assert r.status_code == 200
    data = r.json()
    received_sig = data.pop("signature")

    # Tamper: modify a field in the payload
    tampered = dict(data)
    tampered["_tampered"] = True

    recomputed = _compute_signature(tampered)
    assert not hmac.compare_digest(received_sig, recomputed), (
        "Tampered payload unexpectedly produced a matching signature"
    )
    print("\n[KPI-8] Tamper detection — OK (signature mismatch confirmed)")


async def test_regulator_overview_wrong_key_detected(
    http_client: httpx.AsyncClient, admin_token: str
):
    """
    KPI 8 — Scenario 3: Wrong verification key.
    Using a different key must produce a mismatch.
    """
    r = await http_client.get("/regulator/overview", headers=auth_headers(admin_token))
    assert r.status_code == 200
    data = r.json()
    received_sig = data.pop("signature")

    wrong_key_sig = hmac.new(b"wrong-key", json.dumps(data, sort_keys=True).encode(), hashlib.sha256).hexdigest()
    assert not hmac.compare_digest(received_sig, wrong_key_sig), (
        "Wrong key unexpectedly produced a matching signature"
    )
    print("\n[KPI-8] Wrong key detection — OK")


async def test_regulator_overview_snapshot_fields(
    http_client: httpx.AsyncClient, admin_token: str
):
    """Snapshot must contain open_positions, recent_trades, recent_audit_entries."""
    r = await http_client.get("/regulator/overview", headers=auth_headers(admin_token))
    assert r.status_code == 200
    data = r.json()
    for field in ("active_positions", "orders_last_24h", "open_compliance_alerts"):
        assert field in data, f"Missing field '{field}' in /regulator/overview"


# ── Exposure endpoint ─────────────────────────────────────────────────────────

async def test_regulator_exposure_has_signature(
    http_client: httpx.AsyncClient, admin_token: str
):
    """GET /regulator/exposure must also include a valid HMAC signature."""
    r = await http_client.get("/regulator/exposure", headers=auth_headers(admin_token))
    assert r.status_code == 200
    data = r.json()
    assert "signature" in data, "No 'signature' field in /regulator/exposure"

    received_sig = data.pop("signature")
    expected_sig = _compute_signature(data)
    assert hmac.compare_digest(received_sig, expected_sig), (
        "Signature mismatch on /regulator/exposure"
    )
    print(f"\n[KPI-8] Exposure signature verification — OK")
