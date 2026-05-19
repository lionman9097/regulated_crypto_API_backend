from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from core.security import decode_access_token
from realtime.ws_hub import ws_hub
from schemas.account import (
    AccountSummary,
    LeverageResponse,
    LeverageUpdate,
    MarginTypeUpdate,
    MarginView,
    PositionView,
)
from services.account_service import account_service
from services.binance_service import binance_service


router = APIRouter(prefix="/account", tags=["account"])


@router.get("/{user_id}", response_model=AccountSummary)
async def get_account_summary(user_id: int, db: AsyncSession = Depends(get_db)):
    account = await account_service.sync_balance_from_exchange(db, user_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    positions_with_pnl = await account_service.get_positions_with_pnl(db, user_id)
    available_margin = Decimal(account.balance) - Decimal(account.margin_used)
    total_unrealized_pnl = sum(pnl for _, pnl in positions_with_pnl)

    return {
        "user_id": user_id,
        "balance": float(account.balance),
        "margin_used": float(account.margin_used),
        "available_margin": float(available_margin),
        "total_unrealized_pnl": total_unrealized_pnl,
        "positions": [
            PositionView(
                symbol=position.symbol,
                quantity=float(position.quantity),
                entry_price=float(position.entry_price),
                notional=float(position.notional),
                margin=float(position.margin),
                margin_type=position.margin_type,
                unrealized_pnl=pnl,
                liquidated=position.liquidated,
            )
            for position, pnl in positions_with_pnl
        ],
    }


@router.get("/{user_id}/positions", response_model=list[PositionView])
async def get_positions(user_id: int, db: AsyncSession = Depends(get_db)):
    account = await account_service.get_account(db, user_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    positions_with_pnl = await account_service.get_positions_with_pnl(db, user_id)
    return [
        PositionView(
            symbol=position.symbol,
            quantity=float(position.quantity),
            entry_price=float(position.entry_price),
            notional=float(position.notional),
            margin=float(position.margin),
            margin_type=position.margin_type,
            unrealized_pnl=pnl,
            liquidated=position.liquidated,
        )
        for position, pnl in positions_with_pnl
    ]


@router.get("/{user_id}/margin", response_model=MarginView)
async def get_margin(user_id: int, db: AsyncSession = Depends(get_db)):
    account = await account_service.sync_balance_from_exchange(db, user_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    available_margin = Decimal(account.balance) - Decimal(account.margin_used)
    return {
        "user_id": user_id,
        "balance": float(account.balance),
        "margin_used": float(account.margin_used),
        "available_margin": float(available_margin),
    }


@router.post("/{user_id}/leverage", response_model=LeverageResponse)
async def set_leverage(user_id: int, payload: LeverageUpdate):
    if not binance_service.has_credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exchange integration not configured",
        )
    try:
        result = await binance_service.change_leverage(
            symbol=payload.symbol.upper(),
            leverage=payload.leverage,
        )
        return LeverageResponse(
            symbol=result["symbol"],
            leverage=int(result["leverage"]),
            max_notional_value=str(result.get("maxNotionalValue", "")),
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{user_id}/margin-type", status_code=status.HTTP_200_OK)
async def set_margin_type(
    user_id: int, payload: MarginTypeUpdate, db: AsyncSession = Depends(get_db)
):
    if not binance_service.has_credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exchange integration not configured",
        )
    try:
        await binance_service.change_margin_type(
            symbol=payload.symbol.upper(),
            margin_type=payload.margin_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Reflect the change on any local positions for this symbol
    positions = await account_service.get_positions(db, user_id)
    for pos in positions:
        if pos.symbol == payload.symbol.upper() and not pos.liquidated:
            pos.margin_type = payload.margin_type
    await db.commit()

    return {"detail": f"Margin type for {payload.symbol.upper()} set to {payload.margin_type}"}


@router.websocket("/stream")
async def account_stream(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return

    try:
        decode_access_token(token)
    except ValueError:
        await websocket.close(code=4401, reason="Invalid token")
        return

    await ws_hub.connect_account(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_hub.disconnect_account(websocket)
    except Exception:
        ws_hub.disconnect_account(websocket)

