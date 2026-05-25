from decimal import Decimal

from core.config import settings

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


def get_max_leverage(tier: str = "standard", notional: Decimal = Decimal("0")) -> int:
    """Return the max allowed leverage for *tier* at the given position *notional*.

    Two constraints are applied:
    1. Per-tier global cap capped by ``settings.max_leverage``.
    2. Notional-bracket step-down: larger positions get lower ceiling.
    """
    tier_key = tier.lower() if tier.lower() in _TIER_CAPS else "standard"
    tier_cap = min(_TIER_CAPS[tier_key], max(1, int(settings.max_leverage)))

    for bracket_ceiling, tier_map in _LEVERAGE_BRACKETS:
        if notional <= bracket_ceiling:
            return min(tier_map.get(tier_key, 1), tier_cap)

    return 1
