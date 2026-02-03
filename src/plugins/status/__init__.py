import os
import json
from nonebot import on_command, get_bots
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent

status_cmd = on_command("status", aliases={"状态"}, priority=5, block=True)


def _mask_url(url: str) -> str:
    return (url or "").split("?")[0]


def _admin_user_ids() -> set[int]:
    """Admins allowed to use /status.

    Configure via ADMIN_USER_IDS as JSON list or comma-separated string.
    Default: [375024323]
    """
    raw = os.getenv("ADMIN_USER_IDS", "").strip()
    if not raw:
        return {375024323}

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
        return {375024323}


@status_cmd.handle()
async def handle_status(event: GroupMessageEvent | PrivateMessageEvent):
    # Security: only allow admin in private chat
    if isinstance(event, GroupMessageEvent):
        await status_cmd.finish("（该命令仅管理员私聊可用）")

    admins = _admin_user_ids()
    if int(getattr(event, "user_id", 0) or 0) not in admins:
        await status_cmd.finish("无权限")

    bots = get_bots()
    bot_ids = list(bots.keys())

    base_url = _mask_url(os.getenv("OPENAI_BASE_URL", ""))
    model = os.getenv("OPENAI_MODEL", "")

    msg = (
        "✅ QQBot Status\n"
        f"- bots_connected: {len(bot_ids)} {bot_ids}\n"
        f"- OPENAI_BASE_URL: {base_url or '[empty]'}\n"
        f"- OPENAI_MODEL: {model or '[empty]'}\n"
        f"- MODEL_CHAT_SHORT: {os.getenv('MODEL_CHAT_SHORT','')}\n"
        f"- MODEL_CHAT_LONG: {os.getenv('MODEL_CHAT_LONG','')}\n"
        f"- MODEL_SUMMARY: {os.getenv('MODEL_SUMMARY','')}\n"
        f"- MODEL_IMAGE: {os.getenv('MODEL_IMAGE','')}\n"
    )

    await status_cmd.finish(msg)
