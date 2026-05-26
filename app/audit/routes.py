from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_roles
from audit.model import AuditLog
from audit.schemas import AuditLogEntry
from audit.service import _compute_row_hash

router = APIRouter(prefix="/audit", tags=["audit"])

_RBAC = [require_roles("admin", "regulator")]


@router.get("/logs", response_model=list[AuditLogEntry], dependencies=_RBAC)
async def list_audit_logs(
    event_type: str | None = Query(None, description="Filter by event type"),
    actor_id: int | None = Query(None, description="Filter by actor user ID"),
    severity: str | None = Query(None, description="Filter by severity (INFO|WARN|CRITICAL)"),
    from_ts: datetime | None = Query(None, description="Earliest created_at (ISO-8601)"),
    to_ts: datetime | None = Query(None, description="Latest created_at (ISO-8601)"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if severity:
        stmt = stmt.where(AuditLog.severity == severity)
    if from_ts:
        stmt = stmt.where(AuditLog.created_at >= from_ts)
    if to_ts:
        stmt = stmt.where(AuditLog.created_at <= to_ts)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/logs/{log_id}", response_model=AuditLogEntry, dependencies=_RBAC)
async def get_audit_log(log_id: int, db: AsyncSession = Depends(get_db)) -> AuditLog:
    result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit log not found")
    return entry


@router.get("/verify-chain", dependencies=_RBAC)
async def verify_audit_chain(
    limit: int = Query(default=500, ge=1, le=5000, description="Max rows to verify (oldest-first)"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Walk the audit-log hash chain and verify integrity.

    Returns ``{\"integrity\": \"OK\", \"checked\": N}`` when all hashes match,
    or ``{\"integrity\": \"BROKEN\", \"broken_at_id\": id, \"checked\": N}``
    at the first mismatch.  Rows with a null ``row_hash`` (legacy rows inserted
    before hash-chaining was enabled) are counted but not verified.
    """
    rows_result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.id.asc())
        .limit(limit)
    )
    rows = rows_result.scalars().all()

    checked = 0
    for row in rows:
        if row.row_hash is None:
            # Legacy row — skip hash verification but continue the walk.
            checked += 1
            continue

        expected = _compute_row_hash(
            row.event_type,
            row.actor_id,
            row.created_at,
            row.event_data,
            row.prev_hash,
        )
        if expected != row.row_hash:
            return {"integrity": "BROKEN", "broken_at_id": row.id, "checked": checked}
        checked += 1

    return {"integrity": "OK", "checked": checked}
