"""
tests/helpers.py
────────────────
Shared utility functions used across test modules.
"""

import asyncio
import time
from statistics import mean, quantiles
from typing import Any

import httpx


async def measure_latency(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict | None = None,
    json: dict | None = None,
    n: int = 20,
) -> dict[str, float]:
    """
    Send *n* sequential requests and return latency percentiles in milliseconds.

    Returns:
        {"p50": float, "p95": float, "p99": float, "mean": float, "samples": int}
    """
    durations: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        await client.request(method, url, headers=headers, json=json)
        durations.append((time.perf_counter() - t0) * 1000)

    sorted_d = sorted(durations)
    qs = quantiles(sorted_d, n=100)  # 1st–99th percentile

    return {
        "p50":     qs[49],
        "p95":     qs[94],
        "p99":     qs[98],
        "mean":    mean(durations),
        "samples": n,
    }


async def await_alert(
    client: httpx.AsyncClient,
    token: str,
    alert_type: str,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> dict[str, Any]:
    """
    Poll GET /alerts until an OPEN alert of *alert_type* appears.

    Returns the alert dict.
    Raises TimeoutError if no matching alert appears within *timeout* seconds.
    """
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = await client.get("/alerts", headers=headers, params={"status": "OPEN"})
        if r.status_code == 200:
            for alert in r.json():
                if alert.get("alert_type") == alert_type:
                    return alert
        await asyncio.sleep(poll_interval)
    raise TimeoutError(
        f"Alert '{alert_type}' did not appear within {timeout}s"
    )


async def get_kline_range(
    client: httpx.AsyncClient,
    token: str,
    symbol: str = "BTCUSDT",
) -> float:
    """
    Fetch the last *closed* 1h candle for *symbol* and return the range %.
    range_pct = (high - low) / open * 100
    """
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.get(
        f"/market/candles/{symbol}",
        headers=headers,
        params={"interval": "1h", "limit": 2},
    )
    r.raise_for_status()
    candles = r.json()
    # Binance kline format: [open_time, open, high, low, close, volume, ...]
    # The second-to-last entry is the last *closed* 1h candle.
    if len(candles) < 2:
        return 0.0
    c = candles[-2]  # last closed candle
    open_, high, low = float(c[1]), float(c[2]), float(c[3])
    if open_ <= 0:
        return 0.0
    return (high - low) / open_ * 100.0


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def api_key_headers(key_id: str, secret: str) -> dict[str, str]:
    return {"X-API-Key": key_id, "X-API-Secret": secret}
