import os
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message

from src.utils.auth import admin_user_ids
from src.utils.conversation_memory import conversation_memory

# Admin command: /aclear <qq> [group_id]
# - If in group and group_id omitted, defaults to current group
# - If in private, must specify group_id to clear group-scoped memory
aclear_cmd = on_command("aclear", aliases={"admin_clear", "清空用户", "清空某人"}, priority=5)


def _is_admin(event) -> bool:
    uid = int(getattr(event, "user_id", 0) or 0)
    return uid in admin_user_ids()


@aclear_cmd.handle()
async def handle_aclear(event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    if not _is_admin(event):
        await aclear_cmd.finish("⚠️ 无权限（仅管理员可用）")

    text = args.extract_plain_text().strip()
    if not text:
        await aclear_cmd.finish(
            "用法：/aclear <QQ号> [群号]\n"
            "- 群聊里不填群号：默认清空该群内此人的记忆\n"
            "- 私聊里必须带群号才能清群内记忆（否则清私聊记忆）\n"
            "示例：/aclear 123456789\n"
            "示例：/aclear 123456789 836571848"
        )

    parts = text.split()
    target_qq = parts[0]
    group_id = None
    if len(parts) >= 2:
        group_id = parts[1]

    # Normalize
    try:
        target_qq_int = int(target_qq)
    except Exception:
        await aclear_cmd.finish("⚠️ QQ号格式不正确")

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

    conversation_memory.clear_user(user_key)
    await aclear_cmd.finish(f"✅ 已清空 {scope} 内用户 {target_qq_int} 的个人记忆")
