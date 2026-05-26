"""Volatility monitor.

Tracks the 1-hour candlestick range for each symbol as a proxy for market
volatility, and returns a leverage multiplier that reduces the max-leverage
ceiling during high-volatility periods.

The monitor is updated by the kline stream on every *closed* 1h candle.
Before the first 1h candle closes (~60 min after startup), the modifier
defaults to 1.0 so trading is not blocked during cold-start.
"""

from decimal import Decimal

# (range_pct_upper_bound, leverage_multiplier)
# Evaluated top-to-bottom; the last entry catches anything above 6 %.
_VOLATILITY_BANDS: list[tuple[float, Decimal]] = [
    (3.0, Decimal("1.00")),   # ≤ 3 % range → full leverage
    (6.0, Decimal("0.75")),   # 3–6 % range → 25 % reduction
    (float("inf"), Decimal("0.50")),  # > 6 % range → 50 % reduction
]


class VolatilityMonitor:
    def __init__(self) -> None:
        # symbol (upper) → latest closed-1h candle range %
        self._range_pct: dict[str, float] = {}

    def update(self, symbol: str, interval: str, open_: float, high: float, low: float) -> None:
        """Record the range of a *closed* candle for the given symbol.

        Only 1h candles are used; other intervals are ignored.
        """
        if interval != "1h" or open_ <= 0:
            return
        self._range_pct[symbol.upper()] = (high - low) / open_ * 100.0

    def get_modifier(self, symbol: str) -> Decimal:
        """Return a multiplier in (0, 1] to apply to the base max leverage.

        Returns 1.0 (no reduction) when no 1h candle data is available yet.
        """
        pct = self._range_pct.get(symbol.upper(), 0.0)
        for threshold, multiplier in _VOLATILITY_BANDS:
            if pct <= threshold:
                return multiplier
        return Decimal("0.50")

    def current_range_pct(self, symbol: str) -> float | None:
        """Return the latest recorded 1h range % for a symbol, or None."""
        return self._range_pct.get(symbol.upper())


volatility_monitor = VolatilityMonitor()
