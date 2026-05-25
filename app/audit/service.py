"""
Audit logging service.

emit() is the single public entry-point.  It is synchronous from the caller's
perspective and schedules a fire-and-forget async task so it never blocks or
propagates errors back to business logic.

Event taxonomy
──────────────
AUTH_LOGIN_SUCCESS       AUTH_LOGIN_FAILURE      AUTH_TOKEN_INVALID
ORDER_CREATED            ORDER_CANCELLED         ORDER_CLOSE_REQUESTED
POSITION_LIQUIDATED
ACCOUNT_LEVERAGE_CHANGED ACCOUNT_MARGIN_TYPE_CHANGED
RISK_CHECK_APPROVED      RISK_CHECK_REJECTED
"""

import asyncio
import logging
from datetime import datetime, UTC

from core.config import AsyncSessionLocal
from audit.model import AuditLog

logger = logging.getLogger(__name__)


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
        async with AsyncSessionLocal() as session:
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
                    created_at=datetime.now(UTC),
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
