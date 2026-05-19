from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import redis_client
from models.account import Account, Position
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

        # For limit orders use the submitted limit price; market orders use current price
        if payload.order_type == "limit":
            price = Decimal(str(payload.limit_price))
        else:
            price = Decimal(str(current_price))

        existing_user_exposure = await user_exposure(db, payload.user_id)
        existing_global_exposure = await global_exposure(db)

        risk_result = await self.risk_engine.evaluate_order(
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
        try:
            exchange_order = await binance_service.create_order(
                symbol=payload.symbol,
                side=payload.side,
                order_type=payload.order_type,
                quantity=order_size,
                limit_price=Decimal(str(payload.limit_price)) if payload.limit_price else None,
            )
            exchange_order_id = int(exchange_order.get("orderId")) if exchange_order.get("orderId") else None
            exchange_status = str(exchange_order.get("status", "NEW"))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Binance order failed: {str(exc)}",
            ) from exc

        order = Order(
            user_id=payload.user_id,
            symbol=payload.symbol,
            side=payload.side,
            order_type=payload.order_type,
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

        await db.commit()
        await db.refresh(order)

        return {
            "order": order,
            "required_margin": float(required_margin),
            "user_exposure_after": float(risk_result["user_exposure_after"]),
            "global_exposure_after": float(risk_result["global_exposure_after"]),
        }

    async def close_position(
        self, db: AsyncSession, user_id: int, symbol: str
    ) -> dict:
        symbol = symbol.upper()

        position_stmt = select(Position).where(
            Position.user_id == user_id,
            Position.symbol == symbol,
            Position.liquidated.is_(False),
        )
        position_result = await db.execute(position_stmt)
        position = position_result.scalar_one_or_none()

        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No open position for {symbol}",
            )

        quantity = abs(Decimal(str(position.quantity)))
        # Long positions have positive quantity — close with SELL; short with BUY
        open_side = "BUY" if Decimal(str(position.quantity)) > 0 else "SELL"
        close_side = "SELL" if open_side == "BUY" else "BUY"

        close_price = Decimal(str(await market_service.get_price(symbol)))

        try:
            await binance_service.close_position(
                symbol=symbol,
                side=open_side,
                quantity=quantity,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Binance close position failed: {str(exc)}",
            ) from exc

        account_stmt = select(Account).where(Account.id == position.account_id)
        account_result = await db.execute(account_stmt)
        account = account_result.scalar_one_or_none()
        if account:
            account.margin_used = max(
                Decimal(str(account.margin_used)) - Decimal(str(position.margin)),
                Decimal("0"),
            )

        position.liquidated = True

        close_order = Order(
            user_id=user_id,
            symbol=symbol,
            side=close_side.lower(),
            order_type="market",
            size=quantity,
            leverage=1,
            price=close_price,
            status="FILLED",
        )
        db.add(close_order)
        await db.flush()  # populate close_order.id

        trade = Trade(
            user_id=user_id,
            order_id=close_order.id,
            symbol=symbol,
            side=close_side.lower(),
            size=quantity,
            price=close_price,
            notional=quantity * close_price,
        )
        db.add(trade)

        await db.commit()

        return {
            "symbol": symbol,
            "side": close_side.lower(),
            "quantity": float(quantity),
            "price": float(close_price),
            "detail": "Position closed",
        }

    async def get_open_orders(self, db: AsyncSession, user_id: int) -> list[Order]:
        stmt = select(Order).where(
            Order.user_id == user_id,
            Order.status.not_in(["FILLED", "CANCELED"]),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_order_history(self, db: AsyncSession, user_id: int) -> list[Order]:
        stmt = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

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
        if exchange_order_id:
            try:
                await binance_service.cancel_order(symbol=order.symbol, exchange_order_id=int(exchange_order_id))
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Binance cancel failed: {str(exc)}",
                ) from exc

        order.status = "CANCELED"
        await db.commit()
        await db.refresh(order)
        return order


order_service = OrderService()
