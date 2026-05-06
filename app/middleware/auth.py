from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.security import decode_access_token
from metrics.prometheus import increment_auth_failure


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/metrics", "/docs", "/openapi.json", "/redoc", "/health", "/auth/token"}:
            return await call_next(request)

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
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        request.state.jwt_payload = payload
        request.state.user_id = payload.get("sub")
        return await call_next(request)
