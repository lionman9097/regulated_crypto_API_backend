"""
tests/test_risk_engine.py
──────────────────────────
Unit tests for RiskEngine.evaluate_order() — no HTTP server required.

Covers all 16 boundary cases (R1–R16) from the Chapter 4 test plan,
including the three-step leverage constraints, MMR table, liquidation
price formulas, and exposure limit enforcement.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

# ── app imports (sys.path set in conftest.py) ─────────────────────────────────
# Import all models so SQLAlchemy can resolve every cross-model relationship
# before any mapper is configured.
import models.order   # noqa: F401
import models.trade   # noqa: F401
from models.account import Account
from models.user import User
from risk_engine.engine import RiskEngine
from risk_engine.leverage import get_max_leverage
from risk_engine.margin import (
    liquidation_price,
    maintenance_margin_rate,
    margin_ratio,
    required_margin,
)
from risk_engine.volatility import VolatilityMonitor

pytestmark = pytest.mark.unit


# ── helpers ───────────────────────────────────────────────────────────────────

def make_user(tier: str = "standard") -> User:
    return User(
        id=1,
        username="test",
        password_hash="x",
        tier=tier,
        role="trader",
    )


def make_account(balance: float = 100_000.0, margin_used: float = 0.0) -> Account:
    return Account(
        id=1,
        user_id=1,
        balance=Decimal(str(balance)),
        margin_used=Decimal(str(margin_used)),
    )


async def evaluate(
    tier: str = "standard",
    balance: float = 100_000.0,
    order_size: float = 1.0,
    price: float = 10_000.0,
    side: str = "buy",
    leverage: int = 5,
    user_exposure: float = 0.0,
    global_exposure: float = 0.0,
    symbol: str = "BTCUSDT",
    max_leverage_override: int = 50,
    global_exposure_threshold: float = 10_000_000.0,
) -> dict:
    engine = RiskEngine()
    with patch("risk_engine.leverage.settings") as mock_settings:
        mock_settings.max_leverage = max_leverage_override
        with patch("risk_engine.engine.settings") as mock_engine_settings:
            mock_engine_settings.global_exposure_threshold = global_exposure_threshold
            mock_engine_settings.max_leverage = max_leverage_override
            return await engine.evaluate_order(
                account=make_account(balance),
                user=make_user(tier),
                order_size=Decimal(str(order_size)),
                price=Decimal(str(price)),
                side=side,
                requested_leverage=leverage,
                current_user_exposure=Decimal(str(user_exposure)),
                current_global_exposure=Decimal(str(global_exposure)),
                symbol=symbol,
            )


# ── R1: Standard tier, notional ≤ $10K, leverage=10 ──────────────────────────

@pytest.mark.asyncio
async def test_r1_standard_low_notional_approved():
    """R1: Standard tier, $10K notional, L=10 — approved at full tier cap."""
    result = await evaluate(tier="standard", order_size=1.0, price=10_000.0, leverage=10)
    assert result["approved"] is True
    assert result["leverage"] == 10


# ── R2: Standard tier, notional $15K, leverage=10 → capped to 5 ──────────────

@pytest.mark.asyncio
async def test_r2_standard_mid_notional_bracket_stepdown():
    """R2: $15K notional moves into the 10K–100K bracket → cap steps to 5x."""
    result = await evaluate(tier="standard", order_size=1.5, price=10_000.0, leverage=10)
    assert result["approved"] is True
    assert result["leverage"] == 5


# ── R3: Standard tier, notional $600K, leverage=5 → capped to 1 ──────────────

@pytest.mark.asyncio
async def test_r3_standard_high_notional_bracket_floor():
    """R3: $600K notional exceeds the $500K bracket → cap steps to 1x.
    Global threshold raised to $20M so standard user limit ($1M) > $600K,
    and balance is $700K to cover 100% margin required at 1x leverage."""
    result = await evaluate(
        tier="standard", order_size=60.0, price=10_000.0, leverage=5,
        balance=700_000.0, global_exposure_threshold=20_000_000.0,
    )
    assert result["approved"] is True
    assert result["leverage"] == 1


# ── R4: Professional tier, notional ≤ $10K, leverage=20 ─────────────────────

@pytest.mark.asyncio
async def test_r4_professional_full_leverage():
    """R4: Professional tier, $10K notional, L=20 — approved at tier cap."""
    result = await evaluate(tier="professional", order_size=1.0, price=10_000.0, leverage=20)
    assert result["approved"] is True
    assert result["leverage"] == 20


# ── R5: Institutional tier, notional ≤ $10K, leverage=50 ────────────────────

@pytest.mark.asyncio
async def test_r5_institutional_full_leverage():
    """R5: Institutional tier, $10K notional, L=50 — approved at tier cap."""
    result = await evaluate(
        tier="institutional", order_size=1.0, price=10_000.0,
        leverage=50, max_leverage_override=50,
    )
    assert result["approved"] is True
    assert result["leverage"] == 50


# ── R6: High volatility (r > 6%) reduces L_base=10 → L_eff=5 ────────────────

@pytest.mark.asyncio
async def test_r6_high_volatility_halves_leverage():
    """R6: 1h candle range > 6% applies ×0.50 → floor(10 × 0.5) = 5."""
    monitor = VolatilityMonitor()
    monitor.update("BTCUSDT", "1h", open_=100.0, high=108.0, low=93.0)  # range ≈ 15%
    with patch("risk_engine.leverage.volatility_monitor", monitor):
        result = await evaluate(
            tier="standard", order_size=1.0, price=10_000.0, leverage=10,
        )
    assert result["approved"] is True
    assert result["leverage"] == 5


# ── R7: Moderate volatility (3% < r ≤ 6%) → floor(10 × 0.75) = 7 ────────────

@pytest.mark.asyncio
async def test_r7_moderate_volatility_reduces_leverage():
    """R7: 1h candle range ≈ 4.5% applies ×0.75 → floor(10 × 0.75) = 7."""
    monitor = VolatilityMonitor()
    monitor.update("BTCUSDT", "1h", open_=100.0, high=104.5, low=100.0)  # range = 4.5%
    with patch("risk_engine.leverage.volatility_monitor", monitor):
        result = await evaluate(
            tier="standard", order_size=1.0, price=10_000.0, leverage=10,
        )
    assert result["approved"] is True
    assert result["leverage"] == 7


# ── R8: Low volatility (r ≤ 3%) — no reduction ──────────────────────────────

@pytest.mark.asyncio
async def test_r8_low_volatility_no_reduction():
    """R8: 1h candle range ≤ 3% applies ×1.00 → L_eff = 10."""
    monitor = VolatilityMonitor()
    monitor.update("BTCUSDT", "1h", open_=100.0, high=102.0, low=100.0)  # range = 2%
    with patch("risk_engine.leverage.volatility_monitor", monitor):
        result = await evaluate(
            tier="standard", order_size=1.0, price=10_000.0, leverage=10,
        )
    assert result["approved"] is True
    assert result["leverage"] == 10


# ── R9: Insufficient balance ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_r9_insufficient_balance_rejected():
    """R9: balance=$50, required_margin=$1000/10=$100 → rejected."""
    result = await evaluate(
        balance=50.0, order_size=1.0, price=1_000.0, leverage=10,
    )
    assert result["approved"] is False
    assert "Insufficient balance" in result["reason"]


# ── R10: Global exposure exceeded ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_r10_global_exposure_exceeded():
    """R10: Global cap is $10M; adding $200K to existing $9.9M → rejected."""
    result = await evaluate(
        order_size=20.0, price=10_000.0, leverage=5,
        global_exposure=9_900_000.0,
    )
    assert result["approved"] is False
    assert "Global exposure" in result["reason"]


# ── R11: Per-user exposure exceeded ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_r11_user_exposure_exceeded():
    """R11: Standard tier limit = 5% of $10M = $500K; adding $10K to $495K → rejected."""
    result = await evaluate(
        tier="standard",
        order_size=1.0, price=10_000.0, leverage=5,
        user_exposure=495_000.0,
        global_exposure=495_000.0,
    )
    assert result["approved"] is False
    assert "User exposure" in result["reason"] or "exposure" in result["reason"].lower()


# ── R12: LONG liquidation price formula ──────────────────────────────────────

def test_r12_long_liquidation_price():
    """R12: LONG  P_liq = P_entry × (1 − 1/L + MMR)."""
    entry = Decimal("100")
    lev = 10
    mmr = maintenance_margin_rate(lev)          # 0.0050 at 10x
    expected = entry * (Decimal("1") - Decimal("1") / Decimal(lev) + mmr)
    result = liquidation_price(entry, lev, "buy")
    assert abs(result - expected) < Decimal("0.0001")


# ── R13: SHORT liquidation price formula ─────────────────────────────────────

def test_r13_short_liquidation_price():
    """R13: SHORT P_liq = P_entry × (1 + 1/L − MMR)."""
    entry = Decimal("100")
    lev = 10
    mmr = maintenance_margin_rate(lev)
    expected = entry * (Decimal("1") + Decimal("1") / Decimal(lev) - mmr)
    result = liquidation_price(entry, lev, "sell")
    assert abs(result - expected) < Decimal("0.0001")


# ── R14: MMR at L=3x ─────────────────────────────────────────────────────────

def test_r14_mmr_3x():
    """R14: Leverage 3x falls in the ≤5x band → MMR = 0.75%."""
    assert maintenance_margin_rate(3) == Decimal("0.0075")


# ── R15: MMR at L=15x ────────────────────────────────────────────────────────

def test_r15_mmr_15x():
    """R15: Leverage 15x falls in the ≤20x band → MMR = 0.25%."""
    assert maintenance_margin_rate(15) == Decimal("0.0025")


# ── R16: Margin ratio ≥ 1.0 triggers liquidation ────────────────────────────

def test_r16_margin_ratio_liquidation_threshold():
    """R16: margin_ratio = maintenance_margin / (balance + uPnL) ≥ 1.0 → liquidate."""
    maint = Decimal("1000")
    balance = Decimal("800")
    upnl = Decimal("-300")  # position losing money
    rho = margin_ratio(maint, balance, upnl)
    assert rho >= Decimal("1.0"), f"Expected ratio ≥ 1.0, got {rho}"


# ── required_margin helper ────────────────────────────────────────────────────

def test_required_margin_formula():
    """Initial margin = notional / leverage."""
    size = Decimal("2")
    price = Decimal("50000")
    lev = 10
    m = required_margin(size, price, lev)
    assert m == Decimal("10000")   # 2 * 50000 / 10


def test_required_margin_zero_leverage_raises():
    with pytest.raises(ValueError):
        required_margin(Decimal("1"), Decimal("100"), 0)
