from decimal import Decimal

# (max_leverage_inclusive, maintenance_margin_rate)
# Higher leverage → lower MMR because positions are smaller relative to notional.
_MMR_TABLE: list[tuple[int, Decimal]] = [
    (2,    Decimal("0.0100")),   # 1.00 % at ≤ 2x
    (5,    Decimal("0.0075")),   # 0.75 % at ≤ 5x
    (10,   Decimal("0.0050")),   # 0.50 % at ≤ 10x
    (20,   Decimal("0.0025")),   # 0.25 % at ≤ 20x
    (50,   Decimal("0.0015")),   # 0.15 % at ≤ 50x
    (9999, Decimal("0.0010")),   # 0.10 % above 50x
]


def required_margin(order_size: Decimal, price: Decimal, leverage: int) -> Decimal:
    """Initial margin = notional / leverage."""
    if leverage <= 0:
        raise ValueError("Leverage must be greater than zero")
    return (order_size * price) / Decimal(leverage)


def maintenance_margin_rate(leverage: int) -> Decimal:
    """Return the maintenance margin rate (MMR) for a given leverage level."""
    for max_lev, rate in _MMR_TABLE:
        if leverage <= max_lev:
            return rate
    return Decimal("0.0010")


def liquidation_price(
    entry_price: Decimal,
    leverage: int,
    side: str,
    mmr: Decimal | None = None,
) -> Decimal:
    """Estimated liquidation price (isolated-margin simplified model).

    LONG  : P_liq = entry × (1 − 1/L + MMR)
    SHORT : P_liq = entry × (1 + 1/L − MMR)
    """
    if leverage <= 0:
        raise ValueError("Leverage must be greater than zero")
    if mmr is None:
        mmr = maintenance_margin_rate(leverage)
    lev = Decimal(str(leverage))
    if side.upper() in ("BUY", "LONG"):
        return entry_price * (Decimal("1") - Decimal("1") / lev + mmr)
    return entry_price * (Decimal("1") + Decimal("1") / lev - mmr)


def margin_ratio(
    maintenance_margin: Decimal,
    wallet_balance: Decimal,
    unrealized_pnl: Decimal = Decimal("0"),
) -> Decimal:
    """Margin ratio = maintenance_margin / (wallet_balance + unrealized_pnl).

    Liquidation is triggered when this reaches or exceeds 1.0 (100 %).
    """
    denom = wallet_balance + unrealized_pnl
    if denom <= Decimal("0"):
        return Decimal("Infinity")
    return maintenance_margin / denom
