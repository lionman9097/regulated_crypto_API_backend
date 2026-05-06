from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from schemas.order import OrderCancelResponse, OrderCreate, OrderExecutionResult, OrderResponse
from services.order_service import order_service


router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderExecutionResult)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db)):
    result = await order_service.create_order(db, payload)
    order = result["order"]

    return {
        "order": OrderResponse(
            order_id=order.id,
            user_id=order.user_id,
            symbol=order.symbol,
            side=order.side,
            size=float(order.size),
            leverage=order.leverage,
            price=float(order.price),
            status=order.status,
            created_at=order.created_at,
        ),
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
