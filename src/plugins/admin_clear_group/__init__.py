from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from typing import Union

from src.utils.auth import admin_user_ids
from src.utils.database import db

# Admin-only: clear group context (Tier2)
# Usage:
# - in group: /gclear (clears current group's short context)
# - in private: /gclear <group_id>
gclear_cmd = on_command("gclear", aliases={"清空群上下文", "清空群记忆"}, priority=5)


def _is_admin(event) -> bool:
    uid = int(getattr(event, "user_id", 0) or 0)
    return uid in admin_user_ids()


@gclear_cmd.handle()
async def handle_gclear(event: Union[GroupMessageEvent, PrivateMessageEvent]):
    if not _is_admin(event):
        await gclear_cmd.finish("⚠️ 无权限（仅管理员可用）")

    raw = str(getattr(event, "message", "")).strip()
    parts = raw.split()

    group_id = None
    if isinstance(event, GroupMessageEvent):
        group_id = str(event.group_id)
    else:
        if len(parts) >= 2:
            group_id = parts[1]

    if not group_id:
        await gclear_cmd.finish("用法：群里 /gclear；私聊 /gclear <群号>")

    try:
        conn = db._get_connection()  # type: ignore
        cursor = conn.cursor()
        cursor.execute("DELETE FROM group_context WHERE group_id = ?", (str(group_id),))
        conn.commit()
    except Exception:
        await gclear_cmd.finish("⚠️ 清空失败")

    await gclear_cmd.finish(f"✅ 已清空群({group_id})的短期上下文")
