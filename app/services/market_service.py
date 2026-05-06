import random
from datetime import datetime

from services.binance_service import binance_service


class MarketService:
    def __init__(self) -> None:
        self._prices = {
            "BTCUSDT": 65000.0,
            "ETHUSDT": 3200.0,
        }

    async def get_price(self, symbol: str) -> float:
        symbol = symbol.upper()
        if binance_service.enabled:
            try:
                price = await binance_service.get_price(symbol)
                self._prices[symbol] = float(price)
                return float(price)
            except Exception as exc:
                if symbol not in self._prices:
                    raise ValueError(f"Unsupported symbol or exchange unavailable: {symbol}") from exc

        if symbol not in self._prices:
            raise ValueError(f"Unsupported symbol: {symbol}")
        return self._prices[symbol]

    async def tick(self, symbol: str | None = None) -> dict:
        symbols = [symbol.upper()] if symbol else list(self._prices.keys())
        updated = {}

        if binance_service.enabled:
            for item in symbols:
                try:
                    exchange_price = await binance_service.get_price(item)
                    self._prices[item] = float(exchange_price)
                    updated[item] = {
                        "price": self._prices[item],
                        "timestamp": datetime.utcnow(),
                    }
                except Exception:
                    continue
            if updated:
                return updated

        for item in symbols:
            if item not in self._prices:
                continue
            delta = random.uniform(-0.005, 0.005)
            self._prices[item] = round(self._prices[item] * (1 + delta), 2)
            updated[item] = {
                "price": self._prices[item],
                "timestamp": datetime.utcnow(),
            }
        return updated

    async def snapshot(self) -> dict:
        return {
            symbol: {"price": price, "timestamp": datetime.utcnow()}
            for symbol, price in self._prices.items()
        }


market_service = MarketService()
