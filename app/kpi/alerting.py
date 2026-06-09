"""
KPI Threshold Alerting Service.

check_thresholds() is awaited directly inside the kpi_stream_publisher loop
(already a background task), so it never delays HTTP responses.

Each check cycle:
  - Computes deltas for windowed counters (auth failures, rate limits, liquidations)
  - Evaluates 6 compliance thresholds
  - Creates OPEN alerts with deduplication (one OPEN alert per type at a time)
  - Auto-resolves alerts when the metric normalises
  - Increments Prometheus compliance_alerts_total counter on new alerts
  - Broadcasts alert payload to the regulator WebSocket channel
  - Emits ALERT_TRIGGERED audit event
"""

import asyncio
import logging
from datetime import datetime, UTC
from decimal import Decimal

from sqlalchemy import select

from alerts.model import KpiAlert
from audit.service import emit
from core.config import AsyncSessionLocal, settings
from metrics.prometheus import get_metrics_snapshot, increment_compliance_alert

logger = logging.getLogger(__name__)


class AlertingService:
    def __init__(self) -> None:
        self._prev_auth_failures: int = 0
        self._prev_rate_limit_hits: int = 0
        self._prev_liquidations: int = 0

    async def check_thresholds(
        self,
        system_kpi: dict,
        security_kpi: dict,
        trading_kpi: dict,
    ) -> None:
        # Import here to avoid circular import (ws_hub → alerting → ws_hub)
        from realtime.ws_hub import ws_hub

        snap = get_metrics_snapshot()
        liq_total: int = snap.get("liquidations_total", 0)

        auth_delta = security_kpi["auth_failures"] - self._prev_auth_failures
        rate_delta = security_kpi["rate_limit_hits"] - self._prev_rate_limit_hits
        liq_delta = liq_total - self._prev_liquidations

        # Update before awaits so concurrent calls don't double-count
        self._prev_auth_failures = security_kpi["auth_failures"]
        self._prev_rate_limit_hits = security_kpi["rate_limit_hits"]
        self._prev_liquidations = liq_total

        exposure_pct = (
            (trading_kpi["global_exposure"] / settings.global_exposure_threshold * 100)
            if settings.global_exposure_threshold > 0
            else 0.0
        )

        # (triggered, alert_type, severity, message, metric_value, threshold_value)
        checks: list[tuple[bool, str, str, str, float | None, float | None]] = [
            (
                system_kpi["latency_ms"] > settings.alert_latency_ms_threshold,
                "LATENCY_HIGH",
                "WARN",
                f"Avg latency {system_kpi['latency_ms']:.1f} ms exceeds {settings.alert_latency_ms_threshold} ms threshold",
                system_kpi["latency_ms"],
                settings.alert_latency_ms_threshold,
            ),
            (
                system_kpi["error_rate"] > settings.alert_error_rate_threshold,
                "ERROR_RATE_HIGH",
                "WARN",
                f"Error rate {system_kpi['error_rate']:.2%} exceeds {settings.alert_error_rate_threshold:.2%} threshold",
                system_kpi["error_rate"],
                settings.alert_error_rate_threshold,
            ),
            (
                auth_delta >= settings.alert_auth_failure_per_cycle,
                "AUTH_FAILURE_SPIKE",
                "CRITICAL",
                f"{auth_delta} auth failure(s) in last cycle (threshold: {settings.alert_auth_failure_per_cycle})",
                float(auth_delta),
                float(settings.alert_auth_failure_per_cycle),
            ),
            (
                rate_delta >= settings.alert_rate_limit_per_cycle,
                "RATE_LIMIT_SPIKE",
                "WARN",
                f"{rate_delta} rate-limit violation(s) in last cycle (threshold: {settings.alert_rate_limit_per_cycle})",
                float(rate_delta),
                float(settings.alert_rate_limit_per_cycle),
            ),
            (
                liq_delta >= settings.alert_liquidation_per_cycle,
                "LIQUIDATION_SPIKE",
                "CRITICAL",
                f"{liq_delta} liquidation(s) in last cycle (threshold: {settings.alert_liquidation_per_cycle})",
                float(liq_delta),
                float(settings.alert_liquidation_per_cycle),
            ),
            (
                exposure_pct >= settings.alert_exposure_pct_threshold,
                "EXPOSURE_THRESHOLD_BREACH",
                "CRITICAL",
                f"Global exposure at {exposure_pct:.1f}% of ${settings.global_exposure_threshold:,.0f} limit",
                exposure_pct,
                settings.alert_exposure_pct_threshold,
            ),
        ]

        tasks = []
        for triggered, alert_type, severity, message, metric_value, threshold_value in checks:
            if triggered:
                tasks.append(
                    self._maybe_create_alert(
                        alert_type, severity, message, metric_value, threshold_value, ws_hub
                    )
                )
            else:
                tasks.append(self._maybe_resolve_alert(alert_type))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.exception("Alert task %d failed: %s", i, result)

    async def _maybe_create_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        metric_value: float | None,
        threshold_value: float | None,
        ws_hub,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                existing = await session.execute(
                    select(KpiAlert).where(
                        KpiAlert.alert_type == alert_type,
                        KpiAlert.status == "OPEN",
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    return  # already has an open alert — deduplicate

                alert = KpiAlert(
                    alert_type=alert_type,
                    severity=severity,
                    message=message,
                    metric_value=Decimal(str(metric_value)) if metric_value is not None else None,
                    threshold_value=Decimal(str(threshold_value)) if threshold_value is not None else None,
                    status="OPEN",
                    triggered_at=datetime.now(UTC),
                )
                session.add(alert)
                await session.commit()
                await session.refresh(alert)

            increment_compliance_alert(alert_type, severity)
            emit(
                "ALERT_TRIGGERED",
                event_data={"alert_type": alert_type, "severity": severity, "message": message},
                severity=severity,
            )
            await ws_hub.broadcast_alert(
                {
                    "type": "alert",
                    "alert_type": alert_type,
                    "severity": severity,
                    "message": message,
                    "metric_value": metric_value,
                    "threshold_value": threshold_value,
                    "triggered_at": alert.triggered_at.isoformat(),
                }
            )
            logger.warning("Compliance alert triggered: %s [%s]", alert_type, severity)
        except Exception:
            logger.exception("Failed to create alert [%s]", alert_type)

    async def _maybe_resolve_alert(self, alert_type: str) -> None:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(KpiAlert).where(
                        KpiAlert.alert_type == alert_type,
                        KpiAlert.status.in_(["OPEN", "ACKNOWLEDGED"]),
                    )
                )
                alert = result.scalar_one_or_none()
                if alert:
                    alert.status = "RESOLVED"
                    alert.resolved_at = datetime.now(UTC)
                    await session.commit()
                    logger.info("Alert auto-resolved: %s", alert_type)
        except Exception:
            logger.exception("Failed to resolve alert [%s]", alert_type)


alerting_service = AlertingService()
