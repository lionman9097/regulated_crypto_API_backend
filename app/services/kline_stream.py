"""
Binance kline/candlestick WebSocket stream service.

Subscribes to kline update streams for all tracked symbols x valid intervals via
the Binance combined stream endpoint. On each update it broadcasts the candle to
all connected kline WebSocket clients that are subscribed to that symbol+interval.

Broadcasts are sent for both in-progress and closed candles; the `is_closed` field
allows the frontend to distinguish them.

Combined stream URL format (demo):
  wss://demo-fstream.binance.com/stream?streams=btcusdt@kline_1m/btcusdt@kline_5m/...

Each kline message from Binance:
  {
    "stream": "btcusdt@kline_1m",
    "data": {
      "e": "kline",
      "E": 1638747660000,
      "s": "BTCUSDT",
      "k": {
        "t": 1638747660000,   <- open time (ms)
        "T": 1638747719999,   <- close time (ms)
        "s": "BTCUSDT",
        "i": "1m",
        "o": "47000.00",
        "c": "47100.00",
        "h": "47200.00",
        "l": "46900.00",
        "v": "100.5",
        "x": false            <- is candle closed?
      }
    }
  }
"""

import asyncio
import json
import logging

import websockets

from core.config import settings
from realtime.ws_hub import ws_hub

logger = logging.getLogger(__name__)

VALID_INTERVALS: set[str] = {"1m", "5m", "15m", "1h"}

_RECONNECT_BASE_DELAY = 5
_MAX_RECONNECT_DELAY = 300


class KlineStreamService:
    def __init__(self) -> None:
        self._running = False

    async def start(self) -> None:
        self._running = True
        await self._stream_loop()

    async def stop(self) -> None:
        self._running = False

    async def _stream_loop(self) -> None:
        delay = _RECONNECT_BASE_DELAY
        while self._running:
            try:
                await self._connect_and_process()
                delay = _RECONNECT_BASE_DELAY
            except Exception:
                logger.exception(
                    "Kline stream disconnected; reconnecting in %ss", delay
                )

            if not self._running:
                break

            await asyncio.sleep(delay)
            delay = min(delay * 2, _MAX_RECONNECT_DELAY)

    async def _connect_and_process(self) -> None:
        from services.market_service import TRACKED_SYMBOLS

        symbols = [s.lower() for s in TRACKED_SYMBOLS]
        streams = "/".join(
            f"{symbol}@kline_{interval}"
            for symbol in symbols
            for interval in sorted(VALID_INTERVALS)
        )
        url = f"{settings.binance_ws_base_url}/stream?streams={streams}"

        logger.info("Connecting to kline stream: %s", url)
        async with websockets.connect(url, ping_interval=30, ping_timeout=10) as ws:
            logger.info("Kline stream connected for symbols: %s", symbols)

            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    data = msg.get("data", {})
                    if data.get("e") == "kline":
                        k = data["k"]
                        symbol: str = data["s"]
                        interval: str = k["i"]
                        candle = {
                            "type": "kline",
                            "symbol": symbol,
                            "interval": interval,
                            "open_time": k["t"],
                            "open": float(k["o"]),
                            "high": float(k["h"]),
                            "low": float(k["l"]),
                            "close": float(k["c"]),
                            "volume": float(k["v"]),
                            "close_time": k["T"],
                            "is_closed": k["x"],
                        }
                        await ws_hub.broadcast_kline(symbol, interval, candle)
                except Exception:
                    logger.exception("Error processing kline update")


kline_stream = KlineStreamService()
