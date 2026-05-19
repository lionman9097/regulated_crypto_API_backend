from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_db_session, settings
from core.security import create_access_token, verify_password
from metrics.prometheus import increment_auth_failure
from models.user import User
from schemas.auth import LoginRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db_session)):
    # Fetch user from database
    result = await session.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        increment_auth_failure()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    token = create_access_token(
        subject=str(user.id),
        extra_claims={"username": user.username},
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }
