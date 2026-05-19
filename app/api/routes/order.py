from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from schemas.order import (
    ClosePositionResponse,
    OrderCancelResponse,
    OrderCreate,
    OrderExecutionResult,
    OrderResponse,
)
from services.order_service import order_service


router = APIRouter(prefix="/orders", tags=["orders"])


def _to_order_response(order) -> OrderResponse:
    return OrderResponse(
        order_id=order.id,
        user_id=order.user_id,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        size=float(order.size),
        leverage=order.leverage,
        price=float(order.price),
        status=order.status,
        created_at=order.created_at,
    )


@router.get("/history", response_model=list[OrderResponse])
async def get_order_history(user_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    orders = await order_service.get_order_history(db, user_id)
    return [_to_order_response(o) for o in orders]


@router.get("", response_model=list[OrderResponse])
async def list_open_orders(user_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    orders = await order_service.get_open_orders(db, user_id)
    return [_to_order_response(o) for o in orders]


@router.post("", response_model=OrderExecutionResult)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db)):
    result = await order_service.create_order(db, payload)
    order = result["order"]

    return {
        "order": _to_order_response(order),
        "required_margin": result["required_margin"],
        "user_exposure_after": result["user_exposure_after"],
        "global_exposure_after": result["global_exposure_after"],
    }


@router.post("/{order_id}/cancel", response_model=OrderCancelResponse)
async def cancel_order(order_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    order = await order_service.cancel_order(db, order_id=order_id, user_id=user_id)
    return {
        "order_id": order.id,
        "status": order.status,
        "detail": "Order canceled",
    }


@router.post("/close/{symbol}", response_model=ClosePositionResponse)
async def close_position(symbol: str, user_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    return await order_service.close_position(db, user_id=user_id, symbol=symbol)
