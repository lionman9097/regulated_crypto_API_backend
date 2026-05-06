from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_db_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


def get_api_key(request: Request) -> str:
    api_key = getattr(request.state, "api_key", None)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    return api_key


def get_db_dep(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db
