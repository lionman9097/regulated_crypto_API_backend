from pydantic import BaseModel


class PositionView(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    notional: float
    margin: float
    liquidated: bool


class AccountSummary(BaseModel):
    user_id: int
    balance: float
    margin_used: float
    available_margin: float
    positions: list[PositionView]
