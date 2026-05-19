from pydantic import BaseModel


class SystemKPIResponse(BaseModel):
    latency_ms: float
    error_rate: float
    uptime: float


class TradingKPIResponse(BaseModel):
    total_orders: int
    total_trades: int
    global_exposure: float


class SecurityKPIResponse(BaseModel):
    auth_failures: int
    rate_limit_hits: int
    total_requests: int
