from datetime import datetime

from pydantic import BaseModel


class PriceResponse(BaseModel):
    symbol: str
    price: float
    timestamp: datetime


class MarketSnapshot(BaseModel):
    prices: list[PriceResponse]


class CandleData(BaseModel):
    symbol: str
    interval: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
