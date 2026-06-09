"""
tests/conftest.py
─────────────────
Shared pytest fixtures for the entire test suite.

Integration tests target a *running* server.  Start the stack first:
    docker-compose -f docker/docker-compose.yml up -d
    # or: uvicorn app.main:app --host 0.0.0.0 --port 8000

Then run:
    pytest tests/ -v

APP_BASE_URL defaults to http://localhost:8000 and can be overridden via
the environment or .env.test.
"""

import asyncio
import os
import sys
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from dotenv import load_dotenv

# ── path & env setup (must happen before any app imports) ─────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

# Set valid-format fallbacks so core.config can be imported even when .env.test
# is absent (e.g. when running unit-only tests without a database).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/crypto_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key")
os.environ.setdefault("REPORT_SIGNATURE_KEY", "test-report-sig-key")

# Load .env.test (overrides the defaults above when it exists)
load_dotenv(ROOT / ".env.test", override=True)

# ── constants ─────────────────────────────────────────────────────────────────
APP_BASE_URL: str = os.environ.get("APP_BASE_URL", "http://localhost:8000")

# Seeded credentials (from app/main.py seed_initial_data)
ADMIN_USER = {"username": "admin_1", "password": "adminpass1"}
TRADER_USER = {"username": "trader_1", "password": "password123"}
REGULATOR_USER = {"username": "regulator_1", "password": "regulatorpass1"}
TRADER2_USER = {"username": "trader_2", "password": "password456"}   # professional tier
TRADER3_USER = {"username": "trader_3", "password": "password789"}   # institutional tier


# ── connectivity check ────────────────────────────────────────────────────────

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: pure unit tests, no server required")
    config.addinivalue_line("markers", "integration: requires running server at APP_BASE_URL")


async def _server_is_reachable() -> bool:
    try:
        async with httpx.AsyncClient(base_url=APP_BASE_URL, timeout=5.0) as c:
            r = await c.get("/health")
            return r.status_code == 200
    except Exception:
        return False


# ── session-scoped event loop ─────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Single event loop shared across the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── HTTP client ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def http_client():
    """Persistent httpx.AsyncClient for the whole session."""
    reachable = await _server_is_reachable()
    if not reachable:
        pytest.skip(
            f"Server not reachable at {APP_BASE_URL}. "
            "Start the stack before running integration tests."
        )
    async with httpx.AsyncClient(
        base_url=APP_BASE_URL,
        timeout=30.0,
        limits=httpx.Limits(max_keepalive_connections=0),
    ) as client:
        yield client


# ── auth token fixtures ───────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def admin_token(http_client: httpx.AsyncClient) -> str:
    r = await http_client.post("/auth/login", json=ADMIN_USER)
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["access_token"]


@pytest_asyncio.fixture(scope="session")
async def trader_token(http_client: httpx.AsyncClient) -> str:
    r = await http_client.post("/auth/login", json=TRADER_USER)
    assert r.status_code == 200, f"Trader login failed: {r.text}"
    return r.json()["access_token"]


@pytest_asyncio.fixture(scope="session")
async def regulator_token(http_client: httpx.AsyncClient) -> str:
    r = await http_client.post("/auth/login", json=REGULATOR_USER)
    assert r.status_code == 200, f"Regulator login failed: {r.text}"
    return r.json()["access_token"]


@pytest_asyncio.fixture(scope="session")
async def trader_user_id(http_client: httpx.AsyncClient, trader_token: str) -> int:
    """Return the user-id for trader_1 by parsing the JWT."""
    import base64
    import json
    payload_b64 = trader_token.split(".")[1]
    # Add padding
    payload_b64 += "=" * (-len(payload_b64) % 4)
    data = json.loads(base64.b64decode(payload_b64))
    return int(data["sub"])


# ── API-key fixture ───────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def api_key_pair(http_client: httpx.AsyncClient, trader_token: str):
    """Create a full-permission API key for trader_1; deactivate after test."""
    headers = {"Authorization": f"Bearer {trader_token}"}
    r = await http_client.post(
        "/api-keys",
        json={"label": "pytest-key", "scopes": ["read:market", "read:account", "read:orders", "write:orders"]},
        headers=headers,
    )
    assert r.status_code == 201, f"API key creation failed: {r.text}"
    data = r.json()
    key_id = data["key_id"]
    secret = data["secret"]

    yield key_id, secret

    # Teardown: deactivate the key
    await http_client.delete(f"/api-keys/{key_id}", headers=headers)


@pytest_asyncio.fixture
async def readonly_api_key(http_client: httpx.AsyncClient, trader_token: str):
    """Create a read:market-only API key; deactivate after test."""
    headers = {"Authorization": f"Bearer {trader_token}"}
    r = await http_client.post(
        "/api-keys",
        json={"label": "pytest-readonly", "scopes": ["read:market"]},
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    key_id, secret = data["key_id"], data["secret"]

    yield key_id, secret

    await http_client.delete(f"/api-keys/{key_id}", headers=headers)


# ── order cleanup fixture ─────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def placed_orders(http_client: httpx.AsyncClient, trader_token: str):
    """
    Collect order IDs placed during a test; cancel them all on teardown.
    Usage in tests:
        order_ids = placed_orders
        r = await http_client.post("/orders", ...)
        order_ids.append(r.json()["order"]["order_id"])
    """
    order_ids: list[int] = []
    yield order_ids

    headers = {"Authorization": f"Bearer {trader_token}"}
    for oid in order_ids:
        try:
            await http_client.post(f"/orders/{oid}/cancel", headers=headers)
        except Exception:
            pass  # Best-effort teardown
