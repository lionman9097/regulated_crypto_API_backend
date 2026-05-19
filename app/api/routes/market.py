from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from core.security import decode_access_token
from realtime.ws_hub import ws_hub
from schemas.market import CandleData, MarketSnapshot, PriceResponse
from services.market_service import market_service


router = APIRouter(prefix="/market", tags=["market"])


@router.get("/candles/{symbol}", response_model=list[CandleData])
async def get_candles(
    symbol: str,
    interval: str = Query(...),
    limit: int = Query(default=100, ge=1, le=500),
):
    try:
        candles = await market_service.get_candles(
            symbol=symbol.upper(), interval=interval, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return candles


@router.get("/price/{symbol}", response_model=PriceResponse)
async def get_price(symbol: str):
    try:
        price = await market_service.get_price(symbol.upper())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    snapshot = await market_service.snapshot()
    item = snapshot[symbol.upper()]
    return {
        "symbol": symbol.upper(),
        "price": price,
        "timestamp": item["timestamp"],
    }


@router.post("/tick", response_model=MarketSnapshot)
async def tick_market(symbol: str | None = Query(default=None)):
    updated = await market_service.tick(symbol.upper() if symbol else None)
    if symbol and not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported symbol: {symbol}")

    return {
        "prices": [
            PriceResponse(symbol=item_symbol, price=item_data["price"], timestamp=item_data["timestamp"])
            for item_symbol, item_data in updated.items()
        ]
    }


@router.websocket("/stream")
async def market_stream(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return

    try:
        decode_access_token(token)
    except ValueError:
        await websocket.close(code=4401, reason="Invalid token")
        return

    await ws_hub.connect_market(websocket)

    try:
        snapshot = await market_service.snapshot()
        await websocket.send_json(
            {
                "type": "market_snapshot",
                "prices": [
                    {
                        "symbol": item_symbol,
                        "price": item_data["price"],
                        "timestamp": item_data["timestamp"].isoformat(),
                    }
                    for item_symbol, item_data in snapshot.items()
                ],
            }
        )

        while True:
            # Keep the socket open until the client disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_hub.disconnect_market(websocket)
    except Exception:
        ws_hub.disconnect_market(websocket)
