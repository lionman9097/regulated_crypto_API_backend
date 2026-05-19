from datetime import datetime

from services.binance_service import binance_service

# Default symbols the mark price stream subscribes to.
# Populated into _prices once live data arrives from Binance.
TRACKED_SYMBOLS: set[str] = {"BTCUSDT", "ETHUSDT"}


class MarketService:
    def __init__(self) -> None:
        self._prices: dict[str, float] = {}
        self._stream_active: bool = False

    def set_price(self, symbol: str, price: float) -> None:
        """Called by the Binance mark price WebSocket stream to update cached prices."""
        self._prices[symbol.upper()] = price

    async def get_price(self, symbol: str) -> float:
        symbol = symbol.upper()
        try:
            price = await binance_service.get_price(symbol)
            self._prices[symbol] = float(price)
            return float(price)
        except Exception as exc:
            raise ValueError(f"Unsupported symbol or exchange unavailable: {symbol}") from exc

    async def tick(self, symbol: str | None = None) -> dict:
        symbols = [symbol.upper()] if symbol else list(TRACKED_SYMBOLS)
        updated = {}

        if self._stream_active:
            # WS stream is keeping prices current; broadcast cached values
            for item in symbols:
                if item in self._prices:
                    updated[item] = {
                        "price": self._prices[item],
                        "timestamp": datetime.utcnow(),
                    }
            return updated

        # Fall back to REST polling when stream is not active
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
        return updated

    async def snapshot(self) -> dict:
        return {
            symbol: {"price": price, "timestamp": datetime.utcnow()}
            for symbol, price in self._prices.items()
        }

    async def get_candles(
        self, symbol: str, interval: str, limit: int
    ) -> list[dict]:
        """Return OHLCV candles from Binance ascending by open_time."""
        VALID_INTERVALS = {"1m", "5m", "15m", "1h"}

        symbol = symbol.upper()
        if interval not in VALID_INTERVALS:
            raise ValueError(f"Unsupported interval: {interval}")

        try:
            raw = await binance_service.get_klines(
                symbol=symbol, interval=interval, limit=limit
            )
            return [
                {
                    "symbol": symbol,
                    "interval": interval,
                    "open_time": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
                for row in raw
            ]
        except Exception as exc:
            raise ValueError(str(exc)) from exc


market_service = MarketService()
