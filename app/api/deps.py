from collections.abc import AsyncGenerator
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_db_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


def get_user_id(request: Request) -> int:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user ID")
    return user_id


def get_user_role(request: Request) -> str:
    return getattr(request.state, "role", "trader")


def require_roles(*allowed_roles: str) -> Callable:
    """Route dependency that enforces role-based access control.

    Usage::

        @router.get("/admin/stuff", dependencies=[require_roles("admin", "regulator")])
    """
    def _check(role: str = Depends(get_user_role)) -> None:
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not permitted to access this resource",
            )
    return Depends(_check)


def get_auth_method(request: Request) -> str:
    """Returns the authentication method used: 'jwt' or 'api_key'."""
    return getattr(request.state, "auth_method", "jwt")


def require_scopes(*required_scopes: str) -> Callable:
    """Route dependency that enforces API key scope requirements.

    JWT-authenticated requests bypass scope checks (JWT = full role-based access).
    API-key-authenticated requests must possess every listed scope.

    Usage::

        @router.post("/order", dependencies=[require_scopes("write:orders")])
    """
    def _check(request: Request) -> None:
        if getattr(request.state, "auth_method", "jwt") == "jwt":
            return
        key_scopes: list[str] = getattr(request.state, "scopes", [])
        missing = [s for s in required_scopes if s not in key_scopes]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key is missing required scope(s): {missing}",
            )
    return Depends(_check)


def get_db_dep(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db
