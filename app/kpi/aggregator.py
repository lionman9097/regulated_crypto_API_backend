from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kpi.collector import kpi_collector
from models.account import Position
from models.order import Order
from models.trade import Trade


class KPIAggregator:
    def system_kpi(self) -> dict:
        snapshot = kpi_collector.collect()
        elapsed = snapshot["elapsed_seconds"]
        downtime = snapshot.get("downtime_seconds", 0.0)
        if elapsed > 0:
            uptime = round((elapsed - downtime) / elapsed * 100, 4)
        else:
            uptime = 100.0
        return {
            "latency_ms": snapshot["avg_latency_ms"],
            "error_rate": snapshot["error_rate"],
            "uptime": round(uptime, 2),
        }

    async def trading_kpi(self, db: AsyncSession) -> dict:
        order_count_result = await db.execute(select(func.count(Order.id)))
        trade_count_result = await db.execute(select(func.count(Trade.id)))
        global_exposure_result = await db.execute(
            select(func.coalesce(func.sum(Position.notional), 0)).where(Position.liquidated.is_(False))
        )

        return {
            "total_orders": int(order_count_result.scalar_one() or 0),
            "total_trades": int(trade_count_result.scalar_one() or 0),
            "global_exposure": float(Decimal(global_exposure_result.scalar_one() or 0)),
        }

    def security_kpi(self) -> dict:
        snapshot = kpi_collector.collect()
        return {
            "auth_failures": int(snapshot["auth_failures_total"]),
            "rate_limit_hits": int(snapshot["rate_limit_hits_total"]),
            "total_requests": int(snapshot["requests_total"]),
        }


kpi_aggregator = KPIAggregator()
