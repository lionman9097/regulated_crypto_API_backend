"""
Audit logging service.

emit() is the single public entry-point.  It is synchronous from the caller's
perspective and schedules a fire-and-forget async task so it never blocks or
propagates errors back to business logic.

Each row is linked to its predecessor via a SHA-256 hash chain:
  row_hash  = SHA-256( event_type | actor_id | created_at | event_data | prev_hash )
  prev_hash = row_hash of the immediately preceding row (None for the first row)

This allows integrity verification via GET /audit/verify-chain.

A module-level asyncio.Lock serialises concurrent write tasks so the chain
remains coherent even when many events are emitted in rapid succession.

Event taxonomy
──────────────
AUTH_LOGIN_SUCCESS       AUTH_LOGIN_FAILURE      AUTH_TOKEN_INVALID
ORDER_CREATED            ORDER_CANCELLED         ORDER_CLOSE_REQUESTED
POSITION_LIQUIDATED
ACCOUNT_LEVERAGE_CHANGED ACCOUNT_MARGIN_TYPE_CHANGED
RISK_CHECK_APPROVED      RISK_CHECK_REJECTED
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, UTC

from sqlalchemy import select

from core.config import AsyncSessionLocal
from audit.model import AuditLog

logger = logging.getLogger(__name__)

# Serialise all writes so the hash chain stays coherent.
_write_lock = asyncio.Lock()


def _compute_row_hash(
    event_type: str,
    actor_id: int | None,
    created_at: datetime,
    event_data: dict | None,
    prev_hash: str | None,
) -> str:
    payload = json.dumps(
        {
            "event_type": event_type,
            "actor_id": actor_id,
            "created_at": created_at.isoformat(),
            "event_data": event_data or {},
            "prev_hash": prev_hash or "",
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


async def _write(
    event_type: str,
    actor_id: int | None,
    actor_username: str | None,
    target_type: str | None,
    target_id: str | None,
    ip_address: str | None,
    event_data: dict | None,
    severity: str,
) -> None:
    try:
        async with _write_lock:
            async with AsyncSessionLocal() as session:
                # Fetch the hash from the most-recent row to build the chain.
                latest = await session.execute(
                    select(AuditLog.row_hash)
                    .order_by(AuditLog.id.desc())
                    .limit(1)
                )
                prev_hash: str | None = latest.scalar_one_or_none()

                now = datetime.now(UTC)
                row_hash = _compute_row_hash(
                    event_type, actor_id, now, event_data, prev_hash
                )

                session.add(
                    AuditLog(
                        event_type=event_type,
                        actor_id=actor_id,
                        actor_username=actor_username,
                        target_type=target_type,
                        target_id=target_id,
                        ip_address=ip_address,
                        event_data=event_data,
                        severity=severity,
                        created_at=now,
                        prev_hash=prev_hash,
                        row_hash=row_hash,
                    )
                )
                await session.commit()
    except Exception:
        logger.exception("Audit write failed [event_type=%s]", event_type)


def emit(
    event_type: str,
    *,
    actor_id: int | None = None,
    actor_username: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_address: str | None = None,
    event_data: dict | None = None,
    severity: str = "INFO",
) -> None:
    """Schedule an audit event.  Never raises; never blocks the caller."""
    asyncio.create_task(
        _write(
            event_type=event_type,
            actor_id=actor_id,
            actor_username=actor_username,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            event_data=event_data,
            severity=severity,
        )
    )
