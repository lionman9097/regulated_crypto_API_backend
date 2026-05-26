from datetime import datetime

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: int
    event_type: str
    actor_id: int | None
    actor_username: str | None
    target_type: str | None
    target_id: str | None
    ip_address: str | None
    event_data: dict | None
    severity: str
    created_at: datetime
    prev_hash: str | None
    row_hash: str | None

    model_config = {"from_attributes": True}
