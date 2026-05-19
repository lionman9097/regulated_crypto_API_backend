from typing import Literal

from pydantic import BaseModel, Field


class MarginView(BaseModel):
    user_id: int
    balance: float
    margin_used: float
    available_margin: float


class PositionView(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    notional: float
    margin: float
    margin_type: str
    unrealized_pnl: float
    liquidated: bool


class AccountSummary(BaseModel):
    user_id: int
    balance: float
    margin_used: float
    available_margin: float
    total_unrealized_pnl: float
    positions: list[PositionView]


class LeverageUpdate(BaseModel):
    symbol: str
    leverage: int = Field(..., ge=1, le=125)


class LeverageResponse(BaseModel):
    symbol: str
    leverage: int
    max_notional_value: str


class MarginTypeUpdate(BaseModel):
    symbol: str
    margin_type: Literal["CROSSED", "ISOLATED"]
