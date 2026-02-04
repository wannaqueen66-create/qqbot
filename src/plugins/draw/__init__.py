import os
from nonebot import on_command, get_bot
from nonebot.adapters.onebot.v11 import Message, MessageSegment, GroupMessageEvent, PrivateMessageEvent
from nonebot.params import CommandArg
from nonebot.log import logger

from src.utils.openai_client import openai_client
from src.utils.database import db
from src.utils.auth import admin_user_ids

# /draw <prompt>
draw_cmd = on_command("draw", aliases={"画", "生成图片", "画图"}, priority=5, block=True)


@draw_cmd.handle()
async def handle_draw(event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    if os.getenv("ENABLE_DRAW", "true").lower() not in ("1","true","yes","on"):
        await draw_cmd.finish("⚠️ /draw 已临时关闭（图片额度不足）。")

    uid = str(getattr(event, "user_id", ""))
    if uid and int(uid) not in admin_user_ids():
        window_hours = int(os.getenv("DRAW_RATE_LIMIT_WINDOW_HOURS", "5"))
        max_times = int(os.getenv("DRAW_RATE_LIMIT_MAX", "2"))
        used = db.count_draw_usage(uid, window_hours=window_hours)
        if used >= max_times:
            await draw_cmd.finish(f"⚠️ /draw 使用已达上限：{window_hours} 小时内最多 {max_times} 次。")

    prompt = args.extract_plain_text().strip()
    if not prompt:
        await draw_cmd.finish("用法：/draw <描述>  （例如：/draw 一只戴墨镜的猫）")

    model = os.getenv("MODEL_IMAGE", "gemini-3-pro-image")
    logger.info(f"[draw] model={model} prompt_len={len(prompt)}")

    try:
        res = await openai_client.image_generations(prompt=prompt, model=model)
    except Exception as e:
        logger.error(f"[draw] image generation failed: {type(e).__name__}: {e}")
        await draw_cmd.finish("⚠️ 图片生成失败，请稍后再试。")

    # record usage
    if uid and int(uid) not in admin_user_ids():
        try:
            db.add_draw_usage(uid)
            db.clean_old_draw_usage()
        except Exception as e:
            logger.warning(f"[draw] failed to record usage: {e}")

    # If backend returned URL, send as URL; otherwise assume base64
    if isinstance(res, str) and res.startswith("http"):
        seg = MessageSegment.image(res)
    else:
        seg = MessageSegment.image(f"base64://{res}")

    try:
        bot = get_bot()
        await bot.send(event=event, message=seg)
    except Exception:
        await draw_cmd.finish(seg)

    await draw_cmd.finish()
