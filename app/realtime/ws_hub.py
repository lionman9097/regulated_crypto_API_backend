from __future__ import annotations

from fastapi import WebSocket


class WebSocketHub:
    def __init__(self) -> None:
        self._market_clients: set[WebSocket] = set()
        self._kpi_clients: set[WebSocket] = set()
        self._account_clients: set[WebSocket] = set()

    async def connect_market(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._market_clients.add(websocket)

    async def connect_kpi(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._kpi_clients.add(websocket)

    async def connect_account(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._account_clients.add(websocket)

    def disconnect_market(self, websocket: WebSocket) -> None:
        self._market_clients.discard(websocket)

    def disconnect_kpi(self, websocket: WebSocket) -> None:
        self._kpi_clients.discard(websocket)

    def disconnect_account(self, websocket: WebSocket) -> None:
        self._account_clients.discard(websocket)

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


ws_hub = WebSocketHub()