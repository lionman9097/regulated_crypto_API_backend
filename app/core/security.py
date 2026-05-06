from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError

from core.config import settings


VALID_API_KEYS = {key.strip() for key in settings.api_keys.split(",") if key.strip()}


def is_valid_api_key(api_key: str | None) -> bool:
    if not api_key:
        return False
    return api_key in VALID_API_KEYS


def create_access_token(subject: str, expires_minutes: int | None = None, extra_claims: dict | None = None) -> str:
    expire_delta = timedelta(minutes=expires_minutes or settings.jwt_access_token_expire_minutes)
    expire_at = datetime.now(UTC) + expire_delta

    payload = {
        "sub": subject,
        "iat": datetime.now(UTC),
        "exp": expire_at,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired token") from exc
