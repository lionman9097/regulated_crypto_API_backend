from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    user_id: int
    symbol: str = Field(..., examples=["BTCUSDT", "ETHUSDT"])
    side: Literal["buy", "sell"]
    size: float = Field(..., gt=0)
    leverage: int | None = Field(default=None, ge=1)


class OrderResponse(BaseModel):
    order_id: int
    user_id: int
    symbol: str
    side: str
    size: float
    leverage: int
    price: float
    status: str
    created_at: datetime


class OrderExecutionResult(BaseModel):
    order: OrderResponse
    required_margin: float
    user_exposure_after: float
    global_exposure_after: float


class OrderCancelResponse(BaseModel):
    order_id: int
    status: str
    detail: str
