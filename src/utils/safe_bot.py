from nonebot import get_bot


def safe_get_bot():
    """Return bot if connected else None."""
    try:
        return get_bot()
    except Exception:
        return None
