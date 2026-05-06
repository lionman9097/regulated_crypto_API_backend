from fastapi import APIRouter, HTTPException, Query, status

from schemas.market import MarketSnapshot, PriceResponse
from services.market_service import market_service


router = APIRouter(prefix="/market", tags=["market"])


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
