"""
Binance User Data Stream service.

Maintains a persistent WebSocket connection to the Binance futures user data
stream, renews the listen key every 55 minutes, and handles three event types:

  - MARGIN_CALL        : broadcast a warning to all connected account clients.
  - ORDER_TRADE_UPDATE : detect liquidation orders and apply them to local DB.
  - ACCOUNT_UPDATE     : sync any zero-quantity positions and broadcast balance.

Liquidation detection logic:
  - order type  == "LIQUIDATION"
  - execution   == "CALCULATED"  (Binance's "Liquidation Execution" marker)
  - client id starts with "autoclose-"  (insufficient margin auto-close)
  - client id == "adl_autoclose"        (auto-deleveraging)
"""

import asyncio
import json
import logging
from decimal import Decimal

import websockets

from audit.service import emit
from core.config import AsyncSessionLocal, settings
from metrics.prometheus import increment_liquidation_event
from models.account import Account, Position
from realtime.ws_hub import ws_hub
from services.binance_service import binance_service
from sqlalchemy import select

logger = logging.getLogger(__name__)

_KEEPALIVE_INTERVAL = 55 * 60   # seconds — stream expires after 60 min
_RECONNECT_BASE_DELAY = 5        # seconds
_MAX_RECONNECT_DELAY = 300       # seconds


class UserDataStreamService:
    def __init__(self) -> None:
        self._listen_key: str | None = None
        self._running = False

    @property
    def enabled(self) -> bool:
        return binance_service.has_credentials

    # ------------------------------------------------------------------ #
    # Public lifecycle                                                     #
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        if not self.enabled:
            logger.info("User data stream disabled: Binance credentials not configured")
            return

        self._running = True

        try:
            self._listen_key = await binance_service.new_listen_key()
            logger.info("Listen key obtained")
        except Exception:
            logger.exception("Failed to obtain listen key; user data stream will not start")
            return

        await asyncio.gather(
            self._keepalive_loop(),
            self._stream_loop(),
            return_exceptions=True,
        )

    async def stop(self) -> None:
        self._running = False
        if self._listen_key:
            try:
                await binance_service.close_listen_key()
                logger.info("Listen key closed")
            except Exception:
                logger.warning("Failed to close listen key on shutdown")

    # ------------------------------------------------------------------ #
    # Internal loops                                                       #
    # ------------------------------------------------------------------ #

    async def _keepalive_loop(self) -> None:
        while self._running:
            await asyncio.sleep(_KEEPALIVE_INTERVAL)
            try:
                await binance_service.renew_listen_key()
                logger.debug("Listen key renewed")
            except Exception:
                logger.exception("Failed to renew listen key")

    async def _stream_loop(self) -> None:
        delay = _RECONNECT_BASE_DELAY
        while self._running:
            try:
                await self._connect_and_process()
                delay = _RECONNECT_BASE_DELAY
            except Exception:
                logger.exception("User data stream disconnected; reconnecting in %ss", delay)

            if not self._running:
                break

            await asyncio.sleep(delay)
            delay = min(delay * 2, _MAX_RECONNECT_DELAY)

            # Refresh listen key before reconnecting in case the old one expired.
            try:
                self._listen_key = await binance_service.new_listen_key()
            except Exception:
                logger.exception("Failed to refresh listen key on reconnect")

    async def _connect_and_process(self) -> None:
        url = f"{settings.binance_ws_base_url}/ws/{self._listen_key}"
        logger.info("Connecting to user data stream: %s", url)
        async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
            logger.info("User data stream connected")
            async for raw in ws:
                try:
                    data = json.loads(raw)
                    await self._dispatch(data)
                except Exception:
                    logger.exception("Error processing user data stream event")

    # ------------------------------------------------------------------ #
    # Event dispatch                                                       #
    # ------------------------------------------------------------------ #

    async def _dispatch(self, data: dict) -> None:
        event_type = data.get("e")
        if event_type == "ORDER_TRADE_UPDATE":
            await self._on_order_update(data)
        elif event_type == "ACCOUNT_UPDATE":
            await self._on_account_update(data)
        elif event_type == "MARGIN_CALL":
            await self._on_margin_call(data)

    async def _on_order_update(self, data: dict) -> None:
        order_data = data.get("o", {})
        client_id: str = order_data.get("c", "")
        order_type: str = order_data.get("o", "")
        execution_type: str = order_data.get("x", "")

        is_liquidation = (
            order_type == "LIQUIDATION"
            or execution_type == "CALCULATED"
            or client_id.startswith("autoclose-")
            or client_id == "adl_autoclose"
        )

        if not is_liquidation:
            return

        symbol: str = order_data.get("s", "")
        avg_price: str = order_data.get("ap", "0") or order_data.get("L", "0")

        logger.warning(
            "Liquidation event received symbol=%s client_order_id=%s", symbol, client_id
        )

        await self._apply_liquidation(symbol)

        await ws_hub.broadcast_account(
            {
                "type": "liquidation",
                "symbol": symbol,
                "side": order_data.get("S", "").lower(),
                "quantity": order_data.get("q", "0"),
                "price": avg_price,
                "client_order_id": client_id,
                "timestamp": data.get("E"),
            }
        )

    async def _on_account_update(self, data: dict) -> None:
        update = data.get("a", {})
        reason: str = update.get("m", "")
        positions: list[dict] = update.get("P", [])

        # Any position the exchange reports as zero quantity has been closed;
        # ensure the local DB reflects that.
        for pos in positions:
            if Decimal(str(pos.get("pa", "1"))) == Decimal("0"):
                await self._apply_liquidation(pos.get("s", ""))

        await ws_hub.broadcast_account(
            {
                "type": "account_update",
                "reason": reason,
                "balances": update.get("B", []),
                "positions": positions,
                "timestamp": data.get("E"),
            }
        )

    async def _on_margin_call(self, data: dict) -> None:
        logger.warning(
            "Margin call event received for %d position(s)", len(data.get("p", []))
        )
        await ws_hub.broadcast_account(
            {
                "type": "margin_call",
                "positions": data.get("p", []),
                "timestamp": data.get("E"),
            }
        )

    # ------------------------------------------------------------------ #
    # DB mutation                                                          #
    # ------------------------------------------------------------------ #

    async def _apply_liquidation(self, symbol: str) -> None:
        if not symbol:
            return

        async with AsyncSessionLocal() as db:
            stmt = select(Position).where(
                Position.symbol == symbol,
                Position.liquidated.is_(False),
            )
            result = await db.execute(stmt)
            positions = result.scalars().all()

            if not positions:
                return

            for position in positions:
                position.liquidated = True
                account_stmt = select(Account).where(Account.id == position.account_id)
                account_result = await db.execute(account_stmt)
                account = account_result.scalar_one_or_none()
                if account:
                    account.margin_used = max(
                        Decimal(str(account.margin_used)) - Decimal(str(position.margin)),
                        Decimal("0"),
                    )

            await db.commit()
            logger.info("Marked %d position(s) liquidated for symbol=%s", len(positions), symbol)
            increment_liquidation_event()

            for position in positions:
                emit(
                    "POSITION_LIQUIDATED",
                    target_type="position",
                    target_id=str(position.id),
                    event_data={
                        "symbol": symbol,
                        "user_id": position.user_id,
                        "quantity": str(position.quantity),
                        "notional": str(position.notional),
                    },
                    severity="CRITICAL",
                )


user_data_stream = UserDataStreamService()
