from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message

from src.utils.auth import admin_user_ids
from src.utils.conversation_memory import conversation_memory
from src.utils.database import db

# Admin-only: clear any user's memory
# Usage:
#   /aclear <QQ号> [群号]
# - In group: omit group_id to clear target's memory in current group
# - In private: omit group_id to clear private memory; provide group_id to clear group-scoped memory
admin_clear = on_command("aclear", aliases={"admin_clear", "清空用户", "清空某人", "清除记忆", "清除用户记忆"}, priority=5)


def _is_admin(event) -> bool:
    uid = int(getattr(event, "user_id", 0) or 0)
    return uid in admin_user_ids()


@admin_clear.handle()
async def handle_admin_clear(event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    if not _is_admin(event):
        await admin_clear.finish("⚠️ 无权限（仅管理员可用）")

    text = args.extract_plain_text().strip()
    if not text:
        await admin_clear.finish(
            "用法：/aclear <QQ号> [群号]\n"
            "- 群聊里不填群号：默认清空该群内此人的记忆\n"
            "- 私聊里不填群号：清空私聊记忆\n"
            "- 私聊里填群号：清空该群内记忆\n"
            "示例：/aclear 123456789\n"
            "示例：/aclear 123456789 836571848"
        )

    parts = text.split()
    target_qq = parts[0]
    group_id = parts[1] if len(parts) >= 2 else None

    try:
        target_qq_int = int(target_qq)
    except Exception:
        await admin_clear.finish("⚠️ QQ号格式不正确")

    # Determine which memory key to clear
    if isinstance(event, GroupMessageEvent):
        gid = group_id or str(event.group_id)
        user_key = f"group_{gid}_user_{target_qq_int}"
        scope = f"群({gid})"
    else:
        if group_id:
            user_key = f"group_{group_id}_user_{target_qq_int}"
            scope = f"群({group_id})"
        else:
            user_key = f"user_{target_qq_int}"
            scope = "私聊"

    # Clear Tier1 personal memory
    conversation_memory.clear_user(user_key)

    # Also clear Tier2 group_context for this user (to avoid "memory revive")
    if isinstance(event, GroupMessageEvent):
        try:
            db.clear_group_context_for_user(str(event.group_id), str(target_qq_int))
        except Exception:
            pass

    await admin_clear.finish(f"✅ 已清空 {scope} 内用户 {target_qq_int} 的个人记忆")
