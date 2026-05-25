from __future__ import annotations

from fastapi import WebSocket


class WebSocketHub:
    def __init__(self) -> None:
        self._market_clients: set[WebSocket] = set()
        self._kpi_clients: set[WebSocket] = set()
        self._account_clients: set[WebSocket] = set()
        self._regulator_clients: set[WebSocket] = set()
        # Kline clients keyed by "{SYMBOL}:{interval}", e.g. "BTCUSDT:1m"
        self._kline_clients: dict[str, set[WebSocket]] = {}

    async def connect_market(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._market_clients.add(websocket)

    async def connect_kpi(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._kpi_clients.add(websocket)

    async def connect_account(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._account_clients.add(websocket)

    async def connect_regulator(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._regulator_clients.add(websocket)

    def disconnect_market(self, websocket: WebSocket) -> None:
        self._market_clients.discard(websocket)

    def disconnect_kpi(self, websocket: WebSocket) -> None:
        self._kpi_clients.discard(websocket)

    def disconnect_account(self, websocket: WebSocket) -> None:
        self._account_clients.discard(websocket)

    def disconnect_regulator(self, websocket: WebSocket) -> None:
        self._regulator_clients.discard(websocket)

    async def broadcast_market(self, payload: dict) -> None:
        stale: list[WebSocket] = []
        for client in self._market_clients:
            try:
                await client.send_json(payload)
            except Exception:
                stale.append(client)
        for client in stale:
            self._market_clients.discard(client)

    async def broadcast_kpi(self, payload: dict) -> None:
        stale: list[WebSocket] = []
        for client in self._kpi_clients:
            try:
                await client.send_json(payload)
            except Exception:
                stale.append(client)
        for client in stale:
            self._kpi_clients.discard(client)

    async def broadcast_account(self, payload: dict) -> None:
        stale: list[WebSocket] = []
        for client in self._account_clients:
            try:
                await client.send_json(payload)
            except Exception:
                stale.append(client)
        for client in stale:
            self._account_clients.discard(client)

    async def broadcast_alert(self, payload: dict) -> None:
        """Broadcast compliance alerts to KPI subscribers and regulator subscribers."""
        targets = self._kpi_clients | self._regulator_clients
        stale: list[WebSocket] = []
        for client in targets:
            try:
                await client.send_json(payload)
            except Exception:
                stale.append(client)
        for client in stale:
            self._kpi_clients.discard(client)
            self._regulator_clients.discard(client)

    def _kline_channel(self, symbol: str, interval: str) -> str:
        return f"{symbol.upper()}:{interval}"

    async def connect_kline(
        self, websocket: WebSocket, symbol: str, interval: str
    ) -> None:
        await websocket.accept()
        channel = self._kline_channel(symbol, interval)
        if channel not in self._kline_clients:
            self._kline_clients[channel] = set()
        self._kline_clients[channel].add(websocket)

    def disconnect_kline(
        self, websocket: WebSocket, symbol: str, interval: str
    ) -> None:
        channel = self._kline_channel(symbol, interval)
        if channel in self._kline_clients:
            self._kline_clients[channel].discard(websocket)

    async def broadcast_kline(
        self, symbol: str, interval: str, payload: dict
    ) -> None:
        channel = self._kline_channel(symbol, interval)
        clients = self._kline_clients.get(channel)
        if not clients:
            return
        stale: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(payload)
            except Exception:
                stale.append(client)
        for client in stale:
            clients.discard(client)


ws_hub = WebSocketHub()
