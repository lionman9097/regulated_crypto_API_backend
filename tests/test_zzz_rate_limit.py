"""
Rate-limit integration test — must run LAST to avoid poisoning
downstream tests with an exhausted Redis rate-limit bucket.

File named ``test_zzz_*`` so it sorts after all other test files
alphabetically.
"""

import time as _time

import httpx
import pytest
import redis as sync_redis

from helpers import auth_headers


pytestmark = [pytest.mark.security, pytest.mark.integration]


async def test_rate_limit_triggers_429(
    http_client: httpx.AsyncClient, trader_token: str, trader_user_id: int
):
    """
    When the per-minute rate-limit bucket for a user reaches
    rate_limit_per_minute (default 500 in test config), additional requests must
    receive HTTP 429 Too Many Requests.

    The test directly primes the Redis bucket to 500 so the 501st
    request is guaranteed to be rejected, avoiding timing flakiness.
    """
    minute_bucket = int(_time.time() // 60)

    # ── Determine the exact key the server uses ──────────────────────────
    # The server middleware uses ``principal`` from ``request.state.user_id``
    # (set by AuthMiddleware) or the JWT ``sub`` claim.  Both produce the
    # same string representation as ``trader_user_id`` via f-string.
    redis_key = f"rl:{trader_user_id}:{minute_bucket}"
    print(f"\n[Rate limit] priming key: {redis_key}")

    # ── Prime the bucket at exactly the limit ────────────────────────────
    r_conn = sync_redis.Redis(host="localhost", port=6379, decode_responses=True)
    try:
        r_conn.set(redis_key, 500, ex=61)
    finally:
        r_conn.close()

    # ── 501st request should be rejected ─────────────────────────────────
    headers = auth_headers(trader_token)
    r = await http_client.get("/orders", headers=headers, params={"user_id": str(trader_user_id)})
    assert r.status_code == 429, (
        f"Expected 429 after priming rate-limit bucket, got {r.status_code}: {r.text}"
    )

    # ── Clean up ─────────────────────────────────────────────────────────
    # If the test runs last in the suite, cleanup is not strictly required,
    # but we delete anyway to be a good citizen.
    r_clean = sync_redis.Redis(host="localhost", port=6379, decode_responses=True)
    try:
        deleted = r_clean.delete(redis_key)
        # Server may have also deleted the key due to the 429 response
        # (depending on the middleware implementation); we accept 0 or 1.
        print(f"\n[Rate limit] cleanup: deleted {deleted} key(s)")
    finally:
        r_clean.close()
