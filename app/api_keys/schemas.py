from datetime import datetime

from pydantic import BaseModel, field_validator


# Full catalogue of grantable scopes.
AVAILABLE_SCOPES: frozenset[str] = frozenset(
    {
        "read:market",
        "read:account",
        "read:orders",
        "write:orders",
        "read:kpi",
    }
)

DEFAULT_SCOPES: list[str] = [
    "read:market",
    "read:account",
    "read:orders",
    "write:orders",
]


class ApiKeyCreate(BaseModel):
    label: str = ""
    scopes: list[str] = DEFAULT_SCOPES
    expires_at: datetime | None = None

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        unknown = [s for s in v if s not in AVAILABLE_SCOPES]
        if unknown:
            raise ValueError(
                f"Unknown scopes: {unknown}. Available: {sorted(AVAILABLE_SCOPES)}"
            )
        return v


class ApiKeyCreateResponse(BaseModel):
    """Returned once on key creation or regeneration. The `secret` field is never stored raw."""

    key_id: str
    secret: str
    label: str
    scopes: list[str]
    is_active: bool
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyResponse(BaseModel):
    """Safe representation — never contains the raw secret."""

    key_id: str
    label: str
    scopes: list[str]
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}
