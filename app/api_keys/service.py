import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from api_keys.model import ApiKey
from core.security import pwd_context


class ApiKeyService:
    @staticmethod
    def _generate_pair() -> tuple[str, str, str]:
        """Return ``(key_id, raw_secret, key_hash)``.

        ``key_id``    — 32 hex chars; the public identifier sent as ``X-API-Key``.
        ``raw_secret`` — 64 hex chars; shown to the user once, never persisted.
        ``key_hash``  — PBKDF2-SHA256 hash of ``raw_secret``; persisted in DB.
        """
        key_id = secrets.token_hex(16)
        raw_secret = secrets.token_hex(32)
        key_hash = pwd_context.hash(raw_secret)
        return key_id, raw_secret, key_hash

    async def create_key(
        self,
        db: AsyncSession,
        user_id: int,
        label: str,
        scopes: list[str],
        expires_at: datetime | None,
    ) -> tuple[ApiKey, str]:
        """Create and persist a new API key.

        Returns ``(ApiKey, raw_secret)``.  The caller must present ``raw_secret``
        to the user immediately — it cannot be recovered afterwards.
        """
        key_id, raw_secret, key_hash = self._generate_pair()
        api_key = ApiKey(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            label=label,
            scopes=scopes,
            is_active=True,
            expires_at=expires_at,
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        return api_key, raw_secret

    async def list_keys(self, db: AsyncSession, user_id: int) -> list[ApiKey]:
        result = await db.execute(
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_key_for_user(
        self, db: AsyncSession, key_id: str, user_id: int
    ) -> ApiKey | None:
        result = await db.execute(
            select(ApiKey).where(ApiKey.key_id == key_id, ApiKey.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def deactivate_key(
        self, db: AsyncSession, key_id: str, user_id: int
    ) -> ApiKey | None:
        """Mark the key as inactive. The row is kept for audit purposes."""
        api_key = await self.get_key_for_user(db, key_id, user_id)
        if not api_key:
            return None
        api_key.is_active = False
        await db.commit()
        await db.refresh(api_key)
        return api_key

    async def regenerate_key(
        self, db: AsyncSession, key_id: str, user_id: int
    ) -> tuple[ApiKey, str] | tuple[None, None]:
        """Rotate the secret in-place. The previous secret is immediately invalidated.

        Returns ``(ApiKey, raw_secret)`` on success, ``(None, None)`` if not found.
        """
        api_key = await self.get_key_for_user(db, key_id, user_id)
        if not api_key:
            return None, None
        _, raw_secret, key_hash = self._generate_pair()
        api_key.key_hash = key_hash
        api_key.is_active = True
        await db.commit()
        await db.refresh(api_key)
        return api_key, raw_secret

    async def authenticate(
        self, db: AsyncSession, key_id: str, raw_secret: str
    ) -> ApiKey | None:
        """Verify ``X-API-Key`` + ``X-API-Secret`` credentials.

        Eagerly loads ``api_key.user`` so the caller can read ``user.role`` without
        an additional round-trip.  Returns ``None`` for any failure (invalid id,
        wrong secret, deactivated, expired).
        """
        result = await db.execute(
            select(ApiKey)
            .options(selectinload(ApiKey.user))
            .where(ApiKey.key_id == key_id, ApiKey.is_active == True)  # noqa: E712
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            return None
        if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
            return None
        if not pwd_context.verify(raw_secret, api_key.key_hash):
            return None
        return api_key

    async def touch_last_used(self, db: AsyncSession, key_id: str) -> None:
        """Fire-and-forget: stamp ``last_used_at`` after a successful authentication."""
        result = await db.execute(select(ApiKey).where(ApiKey.key_id == key_id))
        api_key = result.scalar_one_or_none()
        if api_key:
            api_key.last_used_at = datetime.now(UTC)
            await db.commit()


api_key_service = ApiKeyService()
