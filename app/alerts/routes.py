from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alerts.model import KpiAlert
from alerts.schemas import KpiAlertResponse
from api.deps import get_db, require_roles

router = APIRouter(prefix="/alerts", tags=["alerts"])

_READ = [require_roles("admin", "regulator")]
_ADMIN = [require_roles("admin")]


@router.get("", response_model=list[KpiAlertResponse], dependencies=_READ)
async def list_alerts(
    status_filter: str | None = Query(None, alias="status", description="OPEN | ACKNOWLEDGED | RESOLVED"),
    severity: str | None = Query(None, description="INFO | WARN | CRITICAL"),
    alert_type: str | None = Query(None),
    from_ts: datetime | None = Query(None),
    to_ts: datetime | None = Query(None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[KpiAlert]:
    stmt = select(KpiAlert).order_by(KpiAlert.triggered_at.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(KpiAlert.status == status_filter)
    if severity:
        stmt = stmt.where(KpiAlert.severity == severity)
    if alert_type:
        stmt = stmt.where(KpiAlert.alert_type == alert_type)
    if from_ts:
        stmt = stmt.where(KpiAlert.triggered_at >= from_ts)
    if to_ts:
        stmt = stmt.where(KpiAlert.triggered_at <= to_ts)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{alert_id}", response_model=KpiAlertResponse, dependencies=_READ)
async def get_alert(alert_id: int, db: AsyncSession = Depends(get_db)) -> KpiAlert:
    result = await db.execute(select(KpiAlert).where(KpiAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.post("/{alert_id}/acknowledge", response_model=KpiAlertResponse, dependencies=_ADMIN)
async def acknowledge_alert(alert_id: int, db: AsyncSession = Depends(get_db)) -> KpiAlert:
    result = await db.execute(select(KpiAlert).where(KpiAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if alert.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot acknowledge an alert with status '{alert.status}'",
        )
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(alert)
    return alert
