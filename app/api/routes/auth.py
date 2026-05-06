from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from core.config import settings
from core.security import create_access_token
from models.user import User
from schemas.auth import TokenRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.api_key == payload.api_key)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(
        subject=str(user.id),
        extra_claims={"username": user.username, "tier": user.tier},
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }
