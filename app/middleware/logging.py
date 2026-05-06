import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from metrics.prometheus import record_api_error, record_api_request


logger = logging.getLogger("request-logger")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        endpoint = request.url.path
        method = request.method

        try:
            response = await call_next(request)
        except Exception:
            latency = time.perf_counter() - start
            record_api_request(method=method, endpoint=endpoint, status_code=500, latency_seconds=latency)
            record_api_error(method=method, endpoint=endpoint, status_code=500)
            logger.exception(
                "request_failed endpoint=%s status=%s latency_ms=%.2f",
                endpoint,
                500,
                latency * 1000,
            )
            raise

        latency = time.perf_counter() - start
        status_code = response.status_code

        record_api_request(method=method, endpoint=endpoint, status_code=status_code, latency_seconds=latency)
        if status_code >= 400:
            record_api_error(method=method, endpoint=endpoint, status_code=status_code)

        logger.info(
            "request endpoint=%s status=%s latency_ms=%.2f",
            endpoint,
            status_code,
            latency * 1000,
        )
        return response
