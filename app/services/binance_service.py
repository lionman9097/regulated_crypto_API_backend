import asyncio
import logging
import time as _time_module
from decimal import Decimal

from binance.um_futures import UMFutures

from core.config import settings

logger = logging.getLogger(__name__)

# Corrects Docker/VM clock drift vs Binance server. Updated at startup.
_SERVER_TIME_OFFSET_MS: int = 0


def _adjusted_timestamp() -> int:
    # Subtract a 2.5-second safety margin so clock drift never puts us ahead
    # of Binance server time (exchanges accept timestamps within ~5s recvWindow).
    return int(_time_module.time() * 1000) + _SERVER_TIME_OFFSET_MS - 2500


class _TimeCorrectedClient(UMFutures):
    """UMFutures subclass that injects the server-time-corrected timestamp
    directly into every signed request, bypassing the library's own
    get_timestamp() call which uses the raw local clock."""

    def sign_request(self, http_method, url_path, payload=None, special=False):
        if payload is None:
            payload = {}
        payload["timestamp"] = _adjusted_timestamp()
        query_string = self._prepare_params(payload, special)
        payload["signature"] = self._get_sign(query_string)
        return self.send_request(http_method, url_path, payload, special)

    def limited_encoded_sign_request(self, http_method, url_path, payload=None):
        if payload is None:
            payload = {}
        payload["timestamp"] = _adjusted_timestamp()
        query_string = self._prepare_params(payload)
        url_path = (
            url_path + "?" + query_string + "&signature=" + self._get_sign(query_string)
        )
        return self.send_request(http_method, url_path)


class BinanceService:
    def __init__(self) -> None:
        self._client = _TimeCorrectedClient(
            key=settings.binance_api_key or None,
            secret=settings.binance_api_secret or None,
            base_url=settings.binance_base_url,
        )

    @property
    def has_credentials(self) -> bool:
        return bool(settings.binance_api_key and settings.binance_api_secret)

    async def sync_server_time(self) -> None:
        """Fetch Binance server time and correct local clock drift for all signed requests."""
        global _SERVER_TIME_OFFSET_MS

        def _request() -> dict:
            return self._client.time()

        data = await asyncio.to_thread(_request)
        server_ms = int(data["serverTime"])
        local_ms = int(_time_module.time() * 1000)
        _SERVER_TIME_OFFSET_MS = server_ms - local_ms
        logger.info("Binance server time offset applied: %+dms", _SERVER_TIME_OFFSET_MS)

    async def get_price(self, symbol: str) -> Decimal:
        def _request() -> dict:
            return self._client.ticker_price(symbol=symbol)

        data = await asyncio.to_thread(_request)
        return Decimal(str(data["price"]))

    async def get_klines(
        self, symbol: str, interval: str, limit: int = 100
    ) -> list[list]:
        def _request() -> list[list]:
            return self._client.klines(
                symbol=symbol, interval=interval, limit=limit
            )

        return await asyncio.to_thread(_request)

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        limit_price: Decimal | None = None,
    ) -> dict:
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        def _request() -> dict:
            params: dict = {
                "symbol": symbol,
                "side": side.upper(),
                "type": order_type.upper(),
                "quantity": str(quantity),
                "recvWindow": 5000,
            }
            if order_type.upper() == "LIMIT":
                if limit_price is None:
                    raise ValueError("limit_price is required for LIMIT orders")
                params["price"] = str(limit_price)
                params["timeInForce"] = "GTC"
            return self._client.new_order(**params)

        return await asyncio.to_thread(_request)

    async def cancel_order(self, symbol: str, exchange_order_id: int) -> dict:
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        def _request() -> dict:
            return self._client.cancel_order(
                symbol=symbol, orderId=exchange_order_id, recvWindow=5000
            )

        return await asyncio.to_thread(_request)

    # ------------------------------------------------------------------ #
    # User Data Stream – listen key lifecycle                              #
    # ------------------------------------------------------------------ #

    async def new_listen_key(self) -> str:
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        def _request() -> dict:
            return self._client.new_listen_key()

        data = await asyncio.to_thread(_request)
        return str(data["listenKey"])

    async def renew_listen_key(self) -> None:
        if not self.has_credentials:
            return

        def _request() -> None:
            self._client.renew_listen_key()

        await asyncio.to_thread(_request)

    async def close_listen_key(self) -> None:
        if not self.has_credentials:
            return

        def _request() -> None:
            self._client.close_listen_key()

        await asyncio.to_thread(_request)

    # ------------------------------------------------------------------ #
    # Account & position REST endpoints                                    #
    # ------------------------------------------------------------------ #

    async def get_account(self) -> dict:
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        def _request() -> dict:
            return self._client.account()

        return await asyncio.to_thread(_request)

    async def get_position_risk(self, symbol: str | None = None) -> list[dict]:
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        def _request() -> list[dict]:
            params: dict = {}
            if symbol:
                params["symbol"] = symbol
            return self._client.get_position_risk(**params)

        return await asyncio.to_thread(_request)

    async def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        def _request() -> list[dict]:
            params: dict = {}
            if symbol:
                params["symbol"] = symbol
            return self._client.get_open_orders(**params)

        return await asyncio.to_thread(_request)

    # ------------------------------------------------------------------ #
    # Account settings                                                     #
    # ------------------------------------------------------------------ #

    async def close_position(self, symbol: str, side: str, quantity: Decimal) -> dict:
        """Close a position by placing a reduceOnly market order in the opposite direction."""
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        close_side = "SELL" if side.upper() == "BUY" else "BUY"

        def _request() -> dict:
            return self._client.new_order(
                symbol=symbol,
                side=close_side,
                type="MARKET",
                quantity=str(quantity),
                reduceOnly="true",
                recvWindow=5000,
            )

        return await asyncio.to_thread(_request)

    async def change_leverage(self, symbol: str, leverage: int) -> dict:
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        def _request() -> dict:
            return self._client.change_leverage(symbol=symbol, leverage=leverage)

    async def change_margin_type(self, symbol: str, margin_type: str) -> dict:
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        def _request() -> dict:
            return self._client.change_margin_type(symbol=symbol, marginType=margin_type)

        return await asyncio.to_thread(_request)


binance_service = BinanceService()
