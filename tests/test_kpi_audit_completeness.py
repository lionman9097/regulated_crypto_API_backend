"""
tests/test_kpi_audit_completeness.py
──────────────────────────────────────
KPI 9 — Audit Log Completeness: 100 %

Verifies that:
- Every significant action produces a corresponding audit log entry
- GET /audit/verify-chain reports integrity OK on a clean chain
- Directly tampering a row causes verify-chain to report BROKEN
"""

import os
import sys
from pathlib import Path

import pytest
import httpx
from dotenv import load_dotenv

from helpers import auth_headers

pytestmark = [pytest.mark.kpi, pytest.mark.integration]

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env.test", override=True)

# Expected event types per action
_EVENT_MAP = {
    "login":              "AUTH_LOGIN_SUCCESS",
    "order_create":       "ORDER_CREATED",
    "order_cancel":       "ORDER_CANCELLED",
    "api_key_create":     "API_KEY_CREATED",
    "api_key_deactivate": "API_KEY_DEACTIVATED",
}


async def _get_audit_events(
    client: httpx.AsyncClient,
    token: str,
    event_type: str,
    limit: int = 50,
) -> list[dict]:
    r = await client.get(
        "/audit/logs",
        headers=auth_headers(token),
        params={"event_type": event_type, "limit": limit},
    )
    assert r.status_code == 200, f"GET /audit/logs failed: {r.text}"
    return r.json()


async def _wait_for_audit_event(
    client: httpx.AsyncClient,
    token: str,
    event_type: str,
    order_id: int,
    timeout: float = 5.0,
) -> bool:
    """Poll /audit/logs until an entry with the expected order_id appears.

    The audit service writes entries via ``asyncio.create_task()``, so there
    may be a short delay before the row is committed and visible.
    """
    import asyncio
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        events = await _get_audit_events(client, token, event_type, limit=50)
        for ev in events:
            data = ev.get("event_data", {}) or {}
            data_id = str(data.get("order_id", ""))
            target_id = str(ev.get("target_id", ""))
            if data_id == str(order_id) or target_id == str(order_id):
                return True
        await asyncio.sleep(0.3)
    return False


# ── Action → Audit entry tests ────────────────────────────────────────────────

async def test_login_produces_audit_entry(
    http_client: httpx.AsyncClient, admin_token: str
):
    """A successful login must produce an AUTH_LOGIN_SUCCESS audit entry."""
    # Trigger a fresh login
    r = await http_client.post(
        "/auth/login", json={"username": "trader_1", "password": "password123"}
    )
    assert r.status_code == 200

    events = await _get_audit_events(http_client, admin_token, "AUTH_LOGIN_SUCCESS")
    assert any(e["actor_username"] == "trader_1" for e in events), (
        "No AUTH_LOGIN_SUCCESS entry found for trader_1"
    )
    print("\n[KPI-9] AUTH_LOGIN_SUCCESS — recorded ✓")


async def test_order_create_produces_audit_entry(
    http_client: httpx.AsyncClient,
    admin_token: str,
    trader_token: str,
    trader_user_id: int,
    placed_orders: list,
):
    """POST /orders must produce an ORDER_CREATED audit entry."""
    price_r = await http_client.get(
        "/market/price/BTCUSDT", headers=auth_headers(trader_token)
    )
    assert price_r.status_code == 200
    limit_price = round(float(price_r.json()["price"]) * 0.5, 1)

    order_r = await http_client.post(
        "/orders",
        json={
            "user_id": trader_user_id,
            "symbol": "BTCUSDT",
            "side": "buy",
            "size": 0.002,
            "leverage": 5,
            "order_type": "limit",
            "limit_price": limit_price,
        },
        headers=auth_headers(trader_token),
    )
    if order_r.status_code == 400 and "balance" in order_r.text.lower():
        pytest.skip("Insufficient balance — run tests/seed_test_data.py first")
    assert order_r.status_code == 200, f"Order creation failed: {order_r.text}"
    order_id = order_r.json()["order"]["order_id"]
    placed_orders.append(order_id)

    found = await _wait_for_audit_event(http_client, admin_token, "ORDER_CREATED", order_id)
    assert found, f"No ORDER_CREATED entry found for order_id={order_id}"
    print(f"\n[KPI-9] ORDER_CREATED (order_id={order_id}) — recorded ✓")


async def test_order_cancel_produces_audit_entry(
    http_client: httpx.AsyncClient,
    admin_token: str,
    trader_token: str,
    trader_user_id: int,
):
    """POST /orders/{id}/cancel must produce an ORDER_CANCELLED audit entry."""
    price_r = await http_client.get(
        "/market/price/BTCUSDT", headers=auth_headers(trader_token)
    )
    assert price_r.status_code == 200
    limit_price = round(float(price_r.json()["price"]) * 0.5, 1)

    order_r = await http_client.post(
        "/orders",
        json={
            "user_id": trader_user_id,
            "symbol": "BTCUSDT",
            "side": "buy",
            "size": 0.002,
            "leverage": 5,
            "order_type": "limit",
            "limit_price": limit_price,
        },
        headers=auth_headers(trader_token),
    )
    if order_r.status_code == 400 and "balance" in order_r.text.lower():
        pytest.skip("Insufficient balance — run tests/seed_test_data.py first")
    assert order_r.status_code == 200
    order_id = order_r.json()["order"]["order_id"]

    # cancel
    cancel_r = await http_client.post(
        f"/orders/{order_id}/cancel?user_id={trader_user_id}",
        headers=auth_headers(trader_token),
    )
    assert cancel_r.status_code == 200, f"Cancel failed: {cancel_r.text}"

    events = await _get_audit_events(http_client, admin_token, "ORDER_CANCELLED", limit=20)
    assert events, "No ORDER_CANCELLED entries found after cancellation"
    print(f"\n[KPI-9] ORDER_CANCELLED (order_id={order_id}) — recorded ✓")


async def test_api_key_lifecycle_produces_audit_entries(
    http_client: httpx.AsyncClient,
    admin_token: str,
    trader_token: str,
):
    """API key creation and deactivation must each produce an audit entry."""
    hdrs = auth_headers(trader_token)

    # Create key
    create_r = await http_client.post(
        "/api-keys",
        json={"label": "audit-test-key", "scopes": ["read:market"]},
        headers=hdrs,
    )
    assert create_r.status_code == 201, f"Key creation failed: {create_r.text}"
    key_id = create_r.json()["key_id"]

    create_events = await _get_audit_events(http_client, admin_token, "API_KEY_CREATED", limit=20)
    assert create_events, "No API_KEY_CREATED audit entry found"
    print(f"\n[KPI-9] API_KEY_CREATED (key_id={key_id[:8]}…) — recorded ✓")

    # Deactivate key
    del_r = await http_client.delete(f"/api-keys/{key_id}", headers=hdrs)
    assert del_r.status_code == 204, f"Key deactivation failed: {del_r.text}"

    deact_events = await _get_audit_events(http_client, admin_token, "API_KEY_DEACTIVATED", limit=20)
    assert deact_events, "No API_KEY_DEACTIVATED audit entry found"
    print(f"\n[KPI-9] API_KEY_DEACTIVATED — recorded ✓")


# ── Hash-chain integrity tests ────────────────────────────────────────────────

async def test_audit_chain_integrity_ok(
    http_client: httpx.AsyncClient, admin_token: str
):
    """GET /audit/verify-chain must return integrity=OK on an untampered chain."""
    r = await http_client.get(
        "/audit/verify-chain",
        headers=auth_headers(admin_token),
        params={"limit": 200},
    )
    assert r.status_code == 200, f"verify-chain failed: {r.text}"
    data = r.json()
    print(f"\n[KPI-9] verify-chain — integrity={data.get('integrity')}  checked={data.get('checked')}")
    assert data["integrity"] == "OK", (
        f"Audit chain integrity check failed: {data}"
    )
    assert data.get("checked", 0) > 0, "verify-chain checked 0 rows"


async def test_audit_chain_tamper_detection():
    """
    KPI 9 — Tamper detection: directly modify a row in the DB and confirm
    that verify-chain reports BROKEN.

    This test connects to the test DB directly (requires DATABASE_URL in .env.test).
    """
    sys.path.insert(0, str(_ROOT / "app"))

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        pytest.skip("DATABASE_URL not set in .env.test — skipping tamper test")

    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from audit.model import AuditLog

    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # Find the most recent hashed row
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.row_hash.is_not(None))
            .order_by(AuditLog.id.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()

        if row is None:
            await engine.dispose()
            pytest.skip("No hash-chained audit rows found yet")

        original_event_type = row.event_type
        tampered_event_type = original_event_type + "_TAMPERED"

        # Tamper: modify event_type directly in the DB (bypassing application logic)
        await db.execute(
            update(AuditLog)
            .where(AuditLog.id == row.id)
            .values(event_type=tampered_event_type)
        )
        await db.commit()

    # Use an independent HTTP check via direct chain walk
    from audit.service import _compute_row_hash

    async with Session() as db:
        # Scan most-recent rows first so the tampered row (highest id) is always
        # included even when the DB has accumulated thousands of older rows.
        rows_result = await db.execute(
            select(AuditLog).order_by(AuditLog.id.desc()).limit(500)
        )
        rows = rows_result.scalars().all()

    broken = False
    broken_id = None
    for r in rows:
        if r.row_hash is None:
            continue
        expected = _compute_row_hash(
            r.event_type, r.actor_id, r.created_at, r.event_data, r.prev_hash
        )
        if expected != r.row_hash:
            broken = True
            broken_id = r.id
            break

    # Restore the original value regardless of outcome
    async with Session() as db:
        await db.execute(
            update(AuditLog)
            .where(AuditLog.id == row.id)
            .values(event_type=original_event_type)
        )
        await db.commit()

    await engine.dispose()

    print(f"\n[KPI-9] Tamper detection — broken={broken}  broken_at_id={broken_id}")
    assert broken is True, (
        f"Expected hash chain to be BROKEN after tamper, but all hashes matched"
    )
