from datetime import datetime, UTC
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.config import Base


class KpiAlert(Base):
    __tablename__ = "kpi_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    # Status lifecycle: OPEN → ACKNOWLEDGED (operator saw it) → RESOLVED (metric normalised)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_kpi_alerts_type_status", "alert_type", "status"),
        Index("ix_kpi_alerts_severity_status", "severity", "status"),
        Index("ix_kpi_alerts_triggered_at", "triggered_at"),
    )
