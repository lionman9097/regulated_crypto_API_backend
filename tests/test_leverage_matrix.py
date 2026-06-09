"""
tests/test_leverage_matrix.py
──────────────────────────────
Unit tests for get_max_leverage() covering all 12 tier × notional-bracket
combinations from Table 3.3 of the thesis (Chapter 3).

No volatility modifier is applied here (symbol="" disables it).
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from risk_engine.leverage import get_max_leverage

pytestmark = pytest.mark.unit

# ── helper ────────────────────────────────────────────────────────────────────

def max_lev(tier: str, notional: float, max_leverage_setting: int = 50) -> int:
    with patch("risk_engine.leverage.settings") as mock:
        mock.max_leverage = max_leverage_setting
        return get_max_leverage(
            tier=tier,
            notional=Decimal(str(notional)),
            symbol="",          # no volatility modifier
        )


# ── Bracket 1: notional ≤ $10,000 ────────────────────────────────────────────

@pytest.mark.parametrize("tier,expected", [
    ("standard",      10),
    ("professional",  20),
    ("institutional", 50),
])
def test_bracket1_le_10k(tier, expected):
    assert max_lev(tier, 10_000) == expected


# ── Bracket 2: $10,001 – $100,000 ────────────────────────────────────────────

@pytest.mark.parametrize("tier,expected", [
    ("standard",       5),
    ("professional",  10),
    ("institutional", 20),
])
def test_bracket2_10k_to_100k(tier, expected):
    assert max_lev(tier, 50_000) == expected


# ── Bracket 3: $100,001 – $500,000 ───────────────────────────────────────────

@pytest.mark.parametrize("tier,expected", [
    ("standard",       2),
    ("professional",   5),
    ("institutional", 10),
])
def test_bracket3_100k_to_500k(tier, expected):
    assert max_lev(tier, 300_000) == expected


# ── Bracket 4: > $500,000 ────────────────────────────────────────────────────

@pytest.mark.parametrize("tier,expected", [
    ("standard",      1),
    ("professional",  2),
    ("institutional", 5),
])
def test_bracket4_above_500k(tier, expected):
    assert max_lev(tier, 1_000_000) == expected


# ── Boundary values ───────────────────────────────────────────────────────────

def test_exact_bracket1_upper_boundary():
    """$10,000 is exactly at the bracket-1 ceiling → tier cap applies."""
    assert max_lev("standard", 10_000) == 10


def test_just_over_bracket1_boundary():
    """$10,001 crosses into bracket 2 → standard drops to 5x."""
    assert max_lev("standard", 10_001) == 5


def test_exact_bracket2_upper_boundary():
    """$100,000 is at the bracket-2 ceiling → standard=5x."""
    assert max_lev("standard", 100_000) == 5


def test_just_over_bracket2_boundary():
    """$100,001 enters bracket 3 → standard drops to 2x."""
    assert max_lev("standard", 100_001) == 2


def test_global_max_leverage_cap_binds():
    """settings.max_leverage=5 overrides institutional tier cap (50 → 5)."""
    assert max_lev("institutional", 1_000, max_leverage_setting=5) == 5


def test_unknown_tier_defaults_to_standard():
    """Unknown tier string falls back to standard tier caps."""
    assert max_lev("vip_platinum", 10_000) == 10
