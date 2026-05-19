import time
from threading import Lock

from prometheus_client import Counter, Histogram


api_request_latency_seconds = Histogram(
    "api_request_latency_seconds",
    "API request latency in seconds",
    ["method", "endpoint"],
)

api_error_total = Counter(
    "api_error_total",
    "Total API errors",
    ["method", "endpoint", "status_code"],
)

api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"],
)

auth_failures_total = Counter(
    "auth_failures_total",
    "Total authentication failures",
)

rate_limit_hits_total = Counter(
    "rate_limit_hits_total",
    "Total rate limit violations",
)

liquidation_events_total = Counter(
    "liquidation_events_total",
    "Total liquidation events received from Binance",
)

_START_TIME = time.time()
_LOCK = Lock()

_TOTAL_REQUESTS = 0
_TOTAL_ERRORS = 0
_TOTAL_LATENCY_SECONDS = 0.0
_TOTAL_LATENCY_COUNT = 0
_TOTAL_AUTH_FAILURES = 0
_TOTAL_RATE_LIMIT_HITS = 0


def record_api_request(method: str, endpoint: str, status_code: int, latency_seconds: float) -> None:
    global _TOTAL_REQUESTS, _TOTAL_LATENCY_SECONDS, _TOTAL_LATENCY_COUNT
    api_request_latency_seconds.labels(method=method, endpoint=endpoint).observe(latency_seconds)
    api_requests_total.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    with _LOCK:
        _TOTAL_REQUESTS += 1
        _TOTAL_LATENCY_SECONDS += latency_seconds
        _TOTAL_LATENCY_COUNT += 1


def record_api_error(method: str, endpoint: str, status_code: int) -> None:
    global _TOTAL_ERRORS
    api_error_total.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    with _LOCK:
        _TOTAL_ERRORS += 1


def increment_auth_failure() -> None:
    global _TOTAL_AUTH_FAILURES
    auth_failures_total.inc()
    with _LOCK:
        _TOTAL_AUTH_FAILURES += 1


def increment_rate_limit_hit() -> None:
    global _TOTAL_RATE_LIMIT_HITS
    rate_limit_hits_total.inc()
    with _LOCK:
        _TOTAL_RATE_LIMIT_HITS += 1


_TOTAL_LIQUIDATIONS = 0


def increment_liquidation_event() -> None:
    global _TOTAL_LIQUIDATIONS
    liquidation_events_total.inc()
    with _LOCK:
        _TOTAL_LIQUIDATIONS += 1


def get_metrics_snapshot() -> dict:
    with _LOCK:
        avg_latency_ms = (_TOTAL_LATENCY_SECONDS / _TOTAL_LATENCY_COUNT * 1000) if _TOTAL_LATENCY_COUNT else 0.0
        error_rate = (_TOTAL_ERRORS / _TOTAL_REQUESTS) if _TOTAL_REQUESTS else 0.0
        uptime_seconds = time.time() - _START_TIME
        return {
            "requests_total": _TOTAL_REQUESTS,
            "errors_total": _TOTAL_ERRORS,
            "avg_latency_ms": round(avg_latency_ms, 2),
            "error_rate": round(error_rate, 4),
            "uptime_seconds": int(uptime_seconds),
            "auth_failures_total": _TOTAL_AUTH_FAILURES,
            "rate_limit_hits_total": _TOTAL_RATE_LIMIT_HITS,
        }
