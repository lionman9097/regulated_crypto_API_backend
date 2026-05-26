from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext

from core.config import settings


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


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


def sign_payload(data: dict) -> str:
    """Return an HMAC-SHA256 hex digest of the JSON-serialised *data* dict.

    Uses ``settings.report_signature_key`` so the signing key is independent
    of the JWT secret.  The recipient can verify by recomputing the signature
    over the same deterministic JSON (keys sorted, no extra whitespace).
    """
    body = json.dumps(data, sort_keys=True, default=str).encode()
    return hmac.new(
        settings.report_signature_key.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
