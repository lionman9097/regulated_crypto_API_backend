from decimal import Decimal

from core.config import settings
from risk_engine.volatility import volatility_monitor

# Notional brackets: list of (max_notional_inclusive, {tier: max_leverage})
# Evaluated top-to-bottom; the last entry (Infinity) is the catch-all.
_LEVERAGE_BRACKETS: list[tuple[Decimal, dict[str, int]]] = [
    (Decimal("10000"),       {"standard": 10, "professional": 20, "institutional": 50}),
    (Decimal("100000"),      {"standard":  5, "professional": 10, "institutional": 20}),
    (Decimal("500000"),      {"standard":  2, "professional":  5, "institutional": 10}),
    (Decimal("Infinity"),    {"standard":  1, "professional":  2, "institutional":  5}),
]

# Absolute max leverage cap per tier (also bounded by settings.max_leverage)
_TIER_CAPS: dict[str, int] = {
    "standard":      10,
    "professional":  20,
    "institutional": 50,
}


def get_max_leverage(
    tier: str = "standard",
    notional: Decimal = Decimal("0"),
    symbol: str = "",
) -> int:
    """Return the max allowed leverage for *tier* at the given position *notional*.

    Three constraints are applied in order:
    1. Per-tier global cap, bounded by ``settings.max_leverage``.
    2. Notional-bracket step-down: larger positions get a lower ceiling.
    3. Volatility modifier: reduces the ceiling when the 1h candle range
       exceeds defined thresholds (sourced from the live kline stream).
    """
    tier_key = tier.lower() if tier.lower() in _TIER_CAPS else "standard"
    tier_cap = min(_TIER_CAPS[tier_key], max(1, int(settings.max_leverage)))

    base_leverage: int = 1
    for bracket_ceiling, tier_map in _LEVERAGE_BRACKETS:
        if notional <= bracket_ceiling:
            base_leverage = min(tier_map.get(tier_key, 1), tier_cap)
            break

    if symbol:
        modifier = volatility_monitor.get_modifier(symbol)
        adjusted = int(Decimal(str(base_leverage)) * modifier)
        return max(1, adjusted)

    return base_leverage
