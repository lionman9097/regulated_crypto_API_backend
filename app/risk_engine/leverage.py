TIER_MAX_LEVERAGE = {
    "beginner": 5,
    "intermediate": 10,
    "advanced": 20,
}


def get_max_leverage(user_tier: str) -> int:
    return TIER_MAX_LEVERAGE.get(user_tier, 5)
