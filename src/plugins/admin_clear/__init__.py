from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from typing import Union

from src.utils.auth import is_admin_private

# Admin-only: clear any user's memory
admin_clear = on_command("aclear", aliases={"admin_clear", "清除记忆", "清除用户记忆"}, priority=5)


@admin_clear.handle()
async def handle_admin_clear(event: Union[GroupMessageEvent, PrivateMessageEvent]):
    # Only admin in private chat
    if not is_admin_private(event):
        await admin_clear.finish("⚠️ 无权限：仅管理员私聊可用")

    raw = str(getattr(event, "message", "")).strip()
    parts = raw.split()

    if len(parts) < 2:
        await admin_clear.finish(
            "用法：\n"
            "  /aclear user_<QQ号>\n"
            "  /aclear group_<群号>_user_<QQ号>\n"
            "示例：/aclear user_123456"
        )

    target = parts[1].strip()

    if not (target.startswith("user_") or target.startswith("group_")):
        await admin_clear.finish("⚠️ 参数格式不正确：请传 user_<QQ号> 或 group_<群号>_user_<QQ号>")

    from src.utils.conversation_memory import conversation_memory

    conversation_memory.clear_user(target)
    await admin_clear.finish(f"✅ 已清空记忆：{target}")
