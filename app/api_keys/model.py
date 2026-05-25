from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.config import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Public identifier — sent as X-API-Key header; safe to expose in logs.
    key_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    # PBKDF2-SHA256 hash of the raw secret. The raw secret is never persisted.
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # JSON array of scope strings, e.g. ["read:market", "write:orders"]
    scopes: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # One-way relationship — used to resolve user.role during authentication.
    user = relationship("User")
