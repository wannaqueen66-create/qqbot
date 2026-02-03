import os
import json
from typing import Set


def admin_user_ids() -> Set[int]:
    """Admins allowed to use sensitive commands."""
    raw = os.getenv("ADMIN_USER_IDS", "").strip()
    if not raw:
        return set()

    # JSON list
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return {int(x) for x in data}
    except Exception:
        pass

    # comma-separated
    try:
        return {int(x.strip()) for x in raw.split(",") if x.strip()}
    except Exception:
        return set()


def is_admin_private(event) -> bool:
    """Admin-only, private-chat only."""
    # Avoid importing adapter types; use duck-typing
    if getattr(event, "message_type", None) == "group":
        return False
    uid = int(getattr(event, "user_id", 0) or 0)
    return uid in admin_user_ids()
