import time

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.config import redis_client, settings
from core.security import decode_access_token
from metrics.prometheus import increment_rate_limit_hit


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in {"/metrics", "/docs", "/openapi.json", "/redoc", "/health"}:
            return await call_next(request)

        principal = getattr(request.state, "user_id", None)
        if request.url.path == "/auth/login":
            principal = request.client.host if request.client else "anon"
        elif not principal:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.removeprefix("Bearer ").strip()
                try:
                    payload = decode_access_token(token)
                    principal = payload.get("sub")
                except ValueError:
                    principal = None

        if not principal:
            return await call_next(request)

        minute_bucket = int(time.time() // 60)
        redis_key = f"rl:{principal}:{minute_bucket}"

        try:
            count = await redis_client.incr(redis_key)
            if count == 1:
                await redis_client.expire(redis_key, 61)
        except Exception:
            return await call_next(request)

        if count > settings.rate_limit_per_minute:
            increment_rate_limit_hit()
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        return await call_next(request)
