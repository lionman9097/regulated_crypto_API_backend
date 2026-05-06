from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import redis_client
from models.account import Position
from models.order import Order
from models.trade import Trade
from models.user import User
from risk_engine.engine import RiskEngine
from risk_engine.exposure import global_exposure, user_exposure
from schemas.order import OrderCreate
from services.account_service import account_service
from services.binance_service import binance_service
from services.market_service import market_service


class OrderService:
    def __init__(self) -> None:
        self.risk_engine = RiskEngine()

    async def create_order(self, db: AsyncSession, payload: OrderCreate) -> dict:
        user_stmt = select(User).where(User.id == payload.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        account = await account_service.get_or_create_account(db, payload.user_id)

        try:
            current_price = await market_service.get_price(payload.symbol)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        order_size = Decimal(str(payload.size))
        price = Decimal(str(current_price))

        existing_user_exposure = await user_exposure(db, payload.user_id)
        existing_global_exposure = await global_exposure(db)

        risk_result = await self.risk_engine.evaluate_order(
            user=user,
            account=account,
            order_size=order_size,
            price=price,
            requested_leverage=payload.leverage,
            current_user_exposure=existing_user_exposure,
            current_global_exposure=existing_global_exposure,
        )

        if not risk_result["approved"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=risk_result["reason"])

        exchange_order_id: int | None = None
        exchange_status = "FILLED"
        if binance_service.enabled:
            try:
                exchange_order = await binance_service.create_market_order(
                    symbol=payload.symbol,
                    side=payload.side,
                    quantity=order_size,
                )
                exchange_order_id = int(exchange_order.get("orderId")) if exchange_order.get("orderId") else None
                exchange_status = str(exchange_order.get("status", "FILLED"))
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Binance testnet order failed: {str(exc)}",
                ) from exc

        order = Order(
            user_id=payload.user_id,
            symbol=payload.symbol,
            side=payload.side,
            order_type="market",
            size=order_size,
            leverage=risk_result["leverage"],
            price=price,
            status=exchange_status,
        )
        db.add(order)
        await db.flush()

        if exchange_order_id is not None:
            await redis_client.set(f"exchange_order:{order.id}", str(exchange_order_id), ex=86400)

        required_margin = Decimal(risk_result["required_margin"])
        notional = Decimal(risk_result["order_notional"])

        account.margin_used = Decimal(account.margin_used) + required_margin

        position_stmt = select(Position).where(
            Position.user_id == payload.user_id,
            Position.symbol == payload.symbol,
            Position.liquidated.is_(False),
        )
        position_result = await db.execute(position_stmt)
        position = position_result.scalar_one_or_none()

        signed_qty = order_size if payload.side == "buy" else -order_size

        if position:
            new_qty = Decimal(position.quantity) + signed_qty
            position.quantity = new_qty
            position.entry_price = price
            position.notional = abs(new_qty) * price
            position.margin = Decimal(position.margin) + required_margin
        else:
            position = Position(
                account_id=account.id,
                user_id=payload.user_id,
                symbol=payload.symbol,
                quantity=signed_qty,
                entry_price=price,
                notional=abs(signed_qty) * price,
                margin=required_margin,
                liquidated=False,
            )
            db.add(position)

        trade = Trade(
            user_id=payload.user_id,
            order_id=order.id,
            symbol=payload.symbol,
            side=payload.side,
            size=order_size,
            price=price,
            notional=notional,
        )
        db.add(trade)

        await self.risk_engine.simulate_liquidations(db, payload.user_id)
        await db.commit()
        await db.refresh(order)

        return {
            "order": order,
            "required_margin": float(required_margin),
            "user_exposure_after": float(risk_result["user_exposure_after"]),
            "global_exposure_after": float(risk_result["global_exposure_after"]),
        }

    async def cancel_order(self, db: AsyncSession, order_id: int, user_id: int) -> Order:
        stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        if order.status == "FILLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order already filled and cannot be canceled",
            )

        exchange_order_id = await redis_client.get(f"exchange_order:{order.id}")
        if binance_service.enabled and exchange_order_id:
            try:
                await binance_service.cancel_order(symbol=order.symbol, exchange_order_id=int(exchange_order_id))
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Binance testnet cancel failed: {str(exc)}",
                ) from exc

        order.status = "CANCELED"
        await db.commit()
        await db.refresh(order)
        return order


order_service = OrderService()
