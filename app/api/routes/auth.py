from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit.service import emit
from core.config import get_db_session, settings
from core.security import create_access_token, verify_password
from metrics.prometheus import increment_auth_failure
from models.user import User
from schemas.auth import LoginRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, payload: LoginRequest, session: AsyncSession = Depends(get_db_session)):
    ip = request.client.host if request.client else None

    # Fetch user from database
    result = await session.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        increment_auth_failure()
        emit(
            "AUTH_LOGIN_FAILURE",
            actor_username=payload.username,
            ip_address=ip,
            event_data={"reason": "Invalid username or password"},
            severity="WARN",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(
        subject=str(user.id),
        extra_claims={"username": user.username, "role": user.role},
    )

    emit(
        "AUTH_LOGIN_SUCCESS",
        actor_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        event_data={"role": user.role},
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
        "role": user.role,
    }
