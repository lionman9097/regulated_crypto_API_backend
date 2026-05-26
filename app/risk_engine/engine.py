from decimal import Decimal

from core.config import settings
from models.account import Account
from models.user import User
from risk_engine.leverage import get_max_leverage
from risk_engine.margin import (
    liquidation_price,
    maintenance_margin_rate,
    margin_ratio,
    required_margin,
)

# Per-tier user exposure limit as a fraction of the global threshold
_USER_EXPOSURE_FRACTION: dict[str, Decimal] = {
    "standard":      Decimal("0.05"),   #  5 % of global cap
    "professional":  Decimal("0.20"),   # 20 % of global cap
    "institutional": Decimal("0.50"),   # 50 % of global cap
}


class RiskEngine:
    async def evaluate_order(
        self,
        account: Account,
        user: User,
        order_size: Decimal,
        price: Decimal,
        side: str,
        requested_leverage: int | None,
        current_user_exposure: Decimal,
        current_global_exposure: Decimal,
        symbol: str = "",
    ) -> dict:
        if order_size <= 0:
            return {"approved": False, "reason": "Order size must be positive"}

        order_notional = order_size * price
        tier = (user.tier or "standard").lower()

        max_leverage = get_max_leverage(tier=tier, notional=order_notional, symbol=symbol)
        leverage = min(requested_leverage or max_leverage, max_leverage)

        margin_needed = required_margin(order_size, price, leverage)
        available_balance = Decimal(account.balance) - Decimal(account.margin_used)

        if available_balance < margin_needed:
            return {
                "approved": False,
                "reason": "Insufficient balance for required margin",
                "required_margin": float(margin_needed),
                "leverage": leverage,
                "max_leverage_for_tier": max_leverage,
            }

        global_threshold = Decimal(str(settings.global_exposure_threshold))
        if current_global_exposure + order_notional > global_threshold:
            return {
                "approved": False,
                "reason": "Global exposure threshold exceeded",
                "required_margin": float(margin_needed),
                "leverage": leverage,
                "max_leverage_for_tier": max_leverage,
            }

        # Per-user exposure limit derived from the user's tier
        exposure_fraction = _USER_EXPOSURE_FRACTION.get(tier, Decimal("0.05"))
        user_exposure_limit = global_threshold * exposure_fraction
        if current_user_exposure + order_notional > user_exposure_limit:
            return {
                "approved": False,
                "reason": (
                    f"User exposure limit exceeded for tier '{tier}' "
                    f"(limit: {float(user_exposure_limit):,.2f} USDT)"
                ),
                "required_margin": float(margin_needed),
                "leverage": leverage,
                "max_leverage_for_tier": max_leverage,
            }

        mmr = maintenance_margin_rate(leverage)
        maint_margin = order_notional * mmr
        liq_price = liquidation_price(price, leverage, side, mmr)
        mratio = margin_ratio(maint_margin, available_balance)

        return {
            "approved": True,
            "required_margin": margin_needed,
            "order_notional": order_notional,
            "leverage": leverage,
            "max_leverage_for_tier": max_leverage,
            "liquidation_price": liq_price,
            "maintenance_margin": float(maint_margin),
            "maintenance_margin_rate": float(mmr),
            "margin_ratio": float(mratio),
            "user_exposure_after": current_user_exposure + order_notional,
            "global_exposure_after": current_global_exposure + order_notional,
        }


