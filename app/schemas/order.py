from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class OrderCreate(BaseModel):
    user_id: int
    symbol: str = Field(..., examples=["BTCUSDT", "ETHUSDT"])
    side: Literal["buy", "sell"]
    size: float = Field(..., gt=0)
    leverage: int | None = Field(default=None, ge=1)
    order_type: Literal["market", "limit"] = "market"
    limit_price: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_limit_price(self) -> "OrderCreate":
        if self.order_type == "limit" and self.limit_price is None:
            raise ValueError("limit_price is required for limit orders")
        return self


class OrderResponse(BaseModel):
    order_id: int
    user_id: int
    symbol: str
    side: str
    order_type: str
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
    liquidation_price: float
    maintenance_margin: float
    leverage: int
    max_leverage_for_tier: int


class OrderCancelResponse(BaseModel):
    order_id: int
    status: str
    detail: str


class ClosePositionResponse(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: float
    detail: str
