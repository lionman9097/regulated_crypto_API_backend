from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from alerts.model import KpiAlert
from audit.model import AuditLog
from models.account import Account, Position
from models.order import Order
from models.trade import Trade
from models.user import User


class RegulatorService:
    async def get_overview(self, db: AsyncSession) -> dict:
        """Aggregate system-wide compliance snapshot."""
        user_count = await db.scalar(select(func.count()).select_from(User))

        active_positions = await db.scalar(
            select(func.count()).select_from(Position).where(Position.liquidated == False)  # noqa: E712
        )

        total_exposure = await db.scalar(
            select(func.coalesce(func.sum(Position.notional), 0)).where(
                Position.liquidated == False  # noqa: E712
            )
        )

        liquidation_count = await db.scalar(
            select(func.count()).select_from(Position).where(Position.liquidated == True)  # noqa: E712
        )

        open_alerts = await db.scalar(
            select(func.count())
            .select_from(KpiAlert)
            .where(KpiAlert.status.in_(["OPEN", "ACKNOWLEDGED"]))
        )

        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
        orders_24h = await db.scalar(
            select(func.count()).select_from(Order).where(Order.created_at >= cutoff)
        )

        return {
            "total_users": user_count or 0,
            "active_positions": active_positions or 0,
            "total_notional_exposure": str(total_exposure or 0),
            "total_liquidations": liquidation_count or 0,
            "open_compliance_alerts": open_alerts or 0,
            "orders_last_24h": orders_24h or 0,
            "snapshot_at": datetime.now(UTC).isoformat(),
        }

    async def get_all_positions(
        self,
        db: AsyncSession,
        symbol: str | None = None,
        user_id: int | None = None,
        include_liquidated: bool = False,
        limit: int = 200,
    ) -> list[Position]:
        stmt = (
            select(Position)
            .order_by(Position.updated_at.desc())
            .limit(limit)
        )
        if not include_liquidated:
            stmt = stmt.where(Position.liquidated == False)  # noqa: E712
        if symbol:
            stmt = stmt.where(Position.symbol == symbol)
        if user_id is not None:
            stmt = stmt.where(Position.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_exposure_breakdown(self, db: AsyncSession) -> list[dict]:
        """Per-symbol aggregate notional exposure for all live (non-liquidated) positions."""
        rows = await db.execute(
            select(
                Position.symbol,
                func.sum(Position.notional).label("total_notional"),
                func.count().label("position_count"),
            )
            .where(Position.liquidated == False)  # noqa: E712
            .group_by(Position.symbol)
            .order_by(func.sum(Position.notional).desc())
        )
        return [
            {
                "symbol": row.symbol,
                "total_notional": str(row.total_notional),
                "position_count": row.position_count,
            }
            for row in rows
        ]

    async def get_liquidation_history(
        self,
        db: AsyncSession,
        symbol: str | None = None,
        user_id: int | None = None,
        limit: int = 200,
    ) -> list[Position]:
        stmt = (
            select(Position)
            .where(Position.liquidated == True)  # noqa: E712
            .order_by(Position.updated_at.desc())
            .limit(limit)
        )
        if symbol:
            stmt = stmt.where(Position.symbol == symbol)
        if user_id is not None:
            stmt = stmt.where(Position.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_users(
        self,
        db: AsyncSession,
        role: str | None = None,
        limit: int = 200,
    ) -> list[User]:
        stmt = (
            select(User)
            .options(selectinload(User.account))
            .order_by(User.created_at.asc())
            .limit(limit)
        )
        if role:
            stmt = stmt.where(User.role == role)
        result = await db.execute(stmt)
        return list(result.scalars().all())


    async def get_ledger_snapshot(self, db: AsyncSession) -> dict:
        """Return an immutable point-in-time snapshot of all live positions,
        recent trades, and the last 50 audit-log entries.

        The caller should attach an HMAC signature before returning to clients.
        """
        snapshot_at = datetime.now(UTC).isoformat()

        positions_result = await db.execute(
            select(Position)
            .where(Position.liquidated == False)  # noqa: E712
            .order_by(Position.updated_at.desc())
        )
        positions = [
            {
                "id": p.id,
                "user_id": p.user_id,
                "symbol": p.symbol,
                "quantity": str(p.quantity),
                "entry_price": str(p.entry_price),
                "notional": str(p.notional),
                "margin": str(p.margin),
                "margin_type": p.margin_type,
            }
            for p in positions_result.scalars().all()
        ]

        trades_result = await db.execute(
            select(Trade).order_by(Trade.created_at.desc()).limit(100)
        )
        recent_trades = [
            {
                "id": t.id,
                "user_id": t.user_id,
                "symbol": t.symbol,
                "side": t.side,
                "size": str(t.size),
                "price": str(t.price),
                "notional": str(t.notional),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in trades_result.scalars().all()
        ]

        audit_result = await db.execute(
            select(AuditLog).order_by(AuditLog.id.desc()).limit(50)
        )
        audit_tail = [
            {
                "id": a.id,
                "event_type": a.event_type,
                "actor_id": a.actor_id,
                "severity": a.severity,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "row_hash": a.row_hash,
            }
            for a in audit_result.scalars().all()
        ]

        return {
            "snapshot_at": snapshot_at,
            "live_positions": positions,
            "recent_trades": recent_trades,
            "audit_tail": audit_tail,
        }


regulator_service = RegulatorService()
