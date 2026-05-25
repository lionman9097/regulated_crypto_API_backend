from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class KpiAlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    message: str
    metric_value: Decimal | None
    threshold_value: Decimal | None
    status: str
    triggered_at: datetime
    resolved_at: datetime | None
    acknowledged_at: datetime | None
    event_data: dict | None

    model_config = {"from_attributes": True}
