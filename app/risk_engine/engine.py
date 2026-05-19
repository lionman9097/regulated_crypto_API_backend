from decimal import Decimal

from core.config import settings
from models.account import Account
from risk_engine.leverage import get_max_leverage
from risk_engine.margin import required_margin


class RiskEngine:
    async def evaluate_order(
        self,
        account: Account,
        order_size: Decimal,
        price: Decimal,
        requested_leverage: int | None,
        current_user_exposure: Decimal,
        current_global_exposure: Decimal,
    ) -> dict:
        if order_size <= 0:
            return {"approved": False, "reason": "Order size must be positive"}

        max_leverage = get_max_leverage()
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


