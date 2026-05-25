from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from audit.service import emit
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
async def create_order(request: Request, payload: OrderCreate, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else None
    result = await order_service.create_order(db, payload)
    order = result["order"]

    emit(
        "ORDER_CREATED",
        actor_id=payload.user_id,
        target_type="order",
        target_id=str(order.id),
        ip_address=ip,
        event_data={
            "symbol": order.symbol,
            "side": order.side,
            "order_type": order.order_type,
            "size": float(order.size),
            "leverage": order.leverage,
            "price": float(order.price),
        },
    )

    return {
        "order": _to_order_response(order),
        "required_margin": result["required_margin"],
        "user_exposure_after": result["user_exposure_after"],
        "global_exposure_after": result["global_exposure_after"],
        "liquidation_price": result["liquidation_price"],
        "maintenance_margin": result["maintenance_margin"],
        "leverage": result["leverage"],
        "max_leverage_for_tier": result["max_leverage_for_tier"],
    }


@router.post("/{order_id}/cancel", response_model=OrderCancelResponse)
async def cancel_order(request: Request, order_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else None
    order = await order_service.cancel_order(db, order_id=order_id, user_id=user_id)

    emit(
        "ORDER_CANCELLED",
        actor_id=user_id,
        target_type="order",
        target_id=str(order_id),
        ip_address=ip,
        event_data={"symbol": order.symbol, "previous_status": "FILLED"},
    )

    return {
        "order_id": order.id,
        "status": order.status,
        "detail": "Order canceled",
    }


@router.post("/close/{symbol}", response_model=ClosePositionResponse)
async def close_position(request: Request, symbol: str, user_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else None
    result = await order_service.close_position(db, user_id=user_id, symbol=symbol)

    emit(
        "ORDER_CLOSE_REQUESTED",
        actor_id=user_id,
        target_type="position",
        target_id=symbol.upper(),
        ip_address=ip,
        event_data={"symbol": symbol.upper()},
    )

    return result
