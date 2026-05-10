from core.config import settings


def get_max_leverage() -> int:
    return max(1, int(settings.max_leverage))
