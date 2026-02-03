from nonebot import on_command, get_bots
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
import os

status_cmd = on_command("status", aliases={"状态"}, priority=5, block=True)


def _mask_url(url: str) -> str:
    # don't leak query tokens
    return (url or "").split("?")[0]


@status_cmd.handle()
async def handle_status(event: GroupMessageEvent | PrivateMessageEvent):
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
