"""
Binance mark price WebSocket stream service.

Subscribes to mark price updates for all symbols tracked in MarketService via
the Binance combined stream endpoint. On each update it:
  1. Writes the new price into market_service._prices (immediately used by REST
     endpoints and risk calculations).
  2. Broadcasts a "mark_price" event to all connected market WebSocket clients.

When this stream is active, market_service.tick() skips REST polling so we
don't make redundant HTTP calls on top of the live WebSocket feed.

The mark price stream is public — no API credentials are required.

Combined stream URL format (demo):
  wss://demo-fstream.binance.com/stream?streams=btcusdt@markPrice@1s/ethusdt@markPrice@1s

Each message:
  {
    "stream": "btcusdt@markPrice@1s",
    "data": {
      "e": "markPriceUpdate",
      "E": 1704067200000,
      "s": "BTCUSDT",
      "p": "42000.00000000"   <- mark price
    }
  }
"""

import asyncio
import json
import logging

import websockets

from core.config import settings
from realtime.ws_hub import ws_hub
from services.binance_service import binance_service

logger = logging.getLogger(__name__)

_RECONNECT_BASE_DELAY = 5
_MAX_RECONNECT_DELAY = 300


class MarketStreamService:
    def __init__(self) -> None:
        self._running = False

    async def start(self) -> None:
        self._running = True
        await self._stream_loop()

    async def stop(self) -> None:
        self._running = False
        # Import here to avoid module-level circular-import
        from services.market_service import market_service
        market_service._stream_active = False

    async def _stream_loop(self) -> None:
        from services.market_service import market_service

        delay = _RECONNECT_BASE_DELAY
        while self._running:
            try:
                await self._connect_and_process()
                delay = _RECONNECT_BASE_DELAY
            except Exception:
                logger.exception(
                    "Mark price stream disconnected; reconnecting in %ss", delay
                )

            market_service._stream_active = False

            if not self._running:
                break

            await asyncio.sleep(delay)
            delay = min(delay * 2, _MAX_RECONNECT_DELAY)

    async def _connect_and_process(self) -> None:
        from services.market_service import market_service, TRACKED_SYMBOLS

        symbols = [s.lower() for s in TRACKED_SYMBOLS]
        streams = "/".join(f"{s}@markPrice@1s" for s in symbols)
        url = f"{settings.binance_ws_base_url}/stream?streams={streams}"

        logger.info("Connecting to mark price stream: %s", url)
        async with websockets.connect(url, ping_interval=30, ping_timeout=10) as ws:
            market_service._stream_active = True
            logger.info("Mark price stream connected for symbols: %s", symbols)

            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    data = msg.get("data", {})
                    if data.get("e") == "markPriceUpdate":
                        symbol: str = data["s"]
                        price = float(data["p"])
                        market_service.set_price(symbol, price)
                        await ws_hub.broadcast_market(
                            {
                                "type": "mark_price",
                                "symbol": symbol,
                                "price": price,
                                "timestamp": data["E"],
                            }
                        )
                except Exception:
                    logger.exception("Error processing mark price update")


market_stream = MarketStreamService()
