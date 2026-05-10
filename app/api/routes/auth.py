from fastapi import APIRouter, HTTPException, status

from core.config import settings
from core.security import create_access_token, is_valid_api_key
from schemas.auth import TokenRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest):
    if not is_valid_api_key(payload.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(
        subject=payload.api_key,
        extra_claims={"api_key": payload.api_key},
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }
