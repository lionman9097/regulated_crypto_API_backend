import asyncio

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from audit.service import emit
from core.config import AsyncSessionLocal
from core.security import decode_access_token
from metrics.prometheus import increment_auth_failure

_EXEMPT_PATHS = {"/metrics", "/docs", "/openapi.json", "/redoc", "/health", "/auth/login"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # ── API Key authentication ───────────────────────────────────────────
        api_key_id = request.headers.get("X-API-Key", "").strip()
        if api_key_id:
            api_secret = request.headers.get("X-API-Secret", "").strip()
            if not api_secret:
                increment_auth_failure()
                return JSONResponse(
                    status_code=401,
                    content={"detail": "X-API-Secret header required when using X-API-Key"},
                )

            from api_keys.service import api_key_service  # local import avoids circular dep

            try:
                async with AsyncSessionLocal() as db:
                    api_key = await api_key_service.authenticate(db, api_key_id, api_secret)
            except Exception:
                increment_auth_failure()
                return JSONResponse(
                    status_code=500, content={"detail": "Authentication service error"}
                )

            if not api_key:
                increment_auth_failure()
                emit(
                    "API_KEY_AUTH_FAILURE",
                    ip_address=request.client.host if request.client else None,
                    event_data={"key_id": api_key_id, "path": request.url.path},
                    severity="WARN",
                )
                return JSONResponse(
                    status_code=401, content={"detail": "Invalid or expired API key"}
                )

            request.state.user_id = api_key.user_id
            request.state.role = api_key.user.role if api_key.user else "trader"
            request.state.scopes = list(api_key.scopes or [])
            request.state.api_key_id = api_key.key_id
            request.state.auth_method = "api_key"
            request.state.jwt_payload = {}

            asyncio.create_task(_touch_api_key(api_key.key_id))
            return await call_next(request)

        # ── JWT Bearer token authentication ──────────────────────────────────
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            increment_auth_failure()
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})

        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            increment_auth_failure()
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})

        try:
            payload = decode_access_token(token)
        except ValueError:
            increment_auth_failure()
            ip = request.client.host if request.client else None
            emit(
                "AUTH_TOKEN_INVALID",
                ip_address=ip,
                event_data={"path": request.url.path},
                severity="WARN",
            )
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        request.state.jwt_payload = payload
        request.state.user_id = int(payload.get("sub"))
        request.state.role = payload.get("role", "trader")
        request.state.auth_method = "jwt"
        request.state.scopes = []
        return await call_next(request)


async def _touch_api_key(key_id: str) -> None:
    """Fire-and-forget: stamp ``last_used_at`` after a successful API key authentication."""
    try:
        from api_keys.service import api_key_service

        async with AsyncSessionLocal() as db:
            await api_key_service.touch_last_used(db, key_id)
    except Exception:
        pass  # Never propagate errors from background housekeeping
