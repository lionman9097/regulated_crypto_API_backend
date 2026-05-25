from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_user_id
from api_keys.schemas import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse
from api_keys.service import api_key_service
from audit.service import emit

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    request: Request,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new API key.

    The ``secret`` field in the response is shown **exactly once** and cannot be
    retrieved again.  Store it securely before closing this response.
    """
    api_key, raw_secret = await api_key_service.create_key(
        db,
        user_id=user_id,
        label=body.label,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )
    emit(
        "API_KEY_CREATED",
        actor_id=user_id,
        actor_username=getattr(request.state, "jwt_payload", {}).get("username"),
        target_type="api_key",
        target_id=api_key.key_id,
        ip_address=request.client.host if request.client else None,
        event_data={"label": body.label, "scopes": body.scopes},
    )
    return {
        "key_id": api_key.key_id,
        "secret": raw_secret,
        "label": api_key.label,
        "scopes": api_key.scopes,
        "is_active": api_key.is_active,
        "created_at": api_key.created_at,
        "expires_at": api_key.expires_at,
    }


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> list:
    """List all API keys owned by the current user. Secrets are never included."""
    return await api_key_service.list_keys(db, user_id)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_api_key(
    key_id: str,
    request: Request,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deactivate an API key immediately.

    The key row is retained for audit purposes but will no longer authenticate.
    """
    api_key = await api_key_service.deactivate_key(db, key_id=key_id, user_id=user_id)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    emit(
        "API_KEY_DEACTIVATED",
        actor_id=user_id,
        actor_username=getattr(request.state, "jwt_payload", {}).get("username"),
        target_type="api_key",
        target_id=key_id,
        ip_address=request.client.host if request.client else None,
    )


@router.post("/{key_id}/regenerate", response_model=ApiKeyCreateResponse)
async def regenerate_api_key(
    key_id: str,
    request: Request,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Rotate the secret for an existing API key.

    The previous secret is **immediately** invalidated.  The new ``secret`` is
    returned exactly once — store it before closing this response.
    """
    api_key, raw_secret = await api_key_service.regenerate_key(
        db, key_id=key_id, user_id=user_id
    )
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    emit(
        "API_KEY_REGENERATED",
        actor_id=user_id,
        actor_username=getattr(request.state, "jwt_payload", {}).get("username"),
        target_type="api_key",
        target_id=key_id,
        ip_address=request.client.host if request.client else None,
    )
    return {
        "key_id": api_key.key_id,
        "secret": raw_secret,
        "label": api_key.label,
        "scopes": api_key.scopes,
        "is_active": api_key.is_active,
        "created_at": api_key.created_at,
        "expires_at": api_key.expires_at,
    }
