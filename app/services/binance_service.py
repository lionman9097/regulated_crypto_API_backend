import asyncio
from decimal import Decimal

from binance.um_futures import UMFutures

from core.config import settings


class BinanceService:
    def __init__(self) -> None:
        self._client = UMFutures(
            key=settings.binance_api_key or None,
            secret=settings.binance_api_secret or None,
            base_url=settings.binance_base_url,
        )

    @property
    def enabled(self) -> bool:
        return settings.exchange_mode == "binance_demo"

    @property
    def has_credentials(self) -> bool:
        return bool(settings.binance_api_key and settings.binance_api_secret)

    async def get_price(self, symbol: str) -> Decimal:
        def _request() -> dict:
            return self._client.ticker_price(symbol=symbol)

        data = await asyncio.to_thread(_request)
        return Decimal(str(data["price"]))

    async def create_market_order(self, symbol: str, side: str, quantity: Decimal) -> dict:
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        def _request() -> dict:
            return self._client.new_order(
                symbol=symbol,
                side=side.upper(),
                type="MARKET",
                quantity=str(quantity),
            )

        return await asyncio.to_thread(_request)

    async def cancel_order(self, symbol: str, exchange_order_id: int) -> dict:
        if not self.has_credentials:
            raise ValueError("Binance API credentials are not configured")

        def _request() -> dict:
            return self._client.cancel_order(symbol=symbol, orderId=exchange_order_id)

        return await asyncio.to_thread(_request)


binance_service = BinanceService()
