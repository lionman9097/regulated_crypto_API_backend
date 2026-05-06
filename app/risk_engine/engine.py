from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from metrics.prometheus import increment_liquidation_events
from models.account import Account, Position
from models.user import User
from risk_engine.leverage import get_max_leverage
from risk_engine.margin import required_margin


class RiskEngine:
    async def evaluate_order(
        self,
        user: User,
        account: Account,
        order_size: Decimal,
        price: Decimal,
        requested_leverage: int | None,
        current_user_exposure: Decimal,
        current_global_exposure: Decimal,
    ) -> dict:
        if order_size <= 0:
            return {"approved": False, "reason": "Order size must be positive"}

        max_leverage = get_max_leverage(user.tier)
        leverage = requested_leverage or max_leverage
        leverage = min(leverage, max_leverage)

        margin_needed = required_margin(order_size, price, leverage)
        available_balance = Decimal(account.balance) - Decimal(account.margin_used)

        if available_balance < margin_needed:
            return {
                "approved": False,
                "reason": "Insufficient balance for required margin",
                "required_margin": float(margin_needed),
                "leverage": leverage,
            }

        order_notional = order_size * price
        if current_global_exposure + order_notional > Decimal(str(settings.global_exposure_threshold)):
            return {
                "approved": False,
                "reason": "Global exposure threshold exceeded",
                "required_margin": float(margin_needed),
                "leverage": leverage,
            }

        return {
            "approved": True,
            "required_margin": margin_needed,
            "order_notional": order_notional,
            "leverage": leverage,
            "user_exposure_after": current_user_exposure + order_notional,
            "global_exposure_after": current_global_exposure + order_notional,
        }

    async def simulate_liquidations(self, db: AsyncSession, user_id: int) -> int:
        account_stmt = select(Account).where(Account.user_id == user_id)
        account_result = await db.execute(account_stmt)
        account = account_result.scalar_one_or_none()
        if not account:
            return 0

        margin_used = Decimal(account.margin_used)
        if margin_used <= 0:
            return 0

        margin_ratio = (Decimal(account.balance) - margin_used) / margin_used
        if margin_ratio >= Decimal(str(settings.liquidation_threshold)):
            return 0

        positions_stmt = select(Position).where(
            Position.user_id == user_id,
            Position.liquidated.is_(False),
        )
        positions_result = await db.execute(positions_stmt)
        positions = positions_result.scalars().all()

        if not positions:
            return 0

        liquidated_count = 0
        for position in positions:
            position.liquidated = True
            account.margin_used = max(Decimal(account.margin_used) - Decimal(position.margin), Decimal("0"))
            liquidated_count += 1

        if liquidated_count:
            increment_liquidation_events(liquidated_count)

        return liquidated_count
