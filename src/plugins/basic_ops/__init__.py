from nonebot import on_command, get_bot
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.params import CommandArg
from typing import Union
import os

ping = on_command("ping", aliases={"在吗"}, priority=5)
help_cmd = on_command("help", aliases={"帮助", "菜单"}, priority=5)

@ping.handle()
async def handle_ping():
    await ping.finish("在呢")

@help_cmd.handle()
async def handle_help(event: Union[GroupMessageEvent, PrivateMessageEvent]):
    help_text = (
        "🤖 QQ Robot 帮助菜单:\n"
        "------------------------\n"
        "/ping (在吗) - 检查机器人是否在线\n"
        "/help (帮助/菜单) - 显示此帮助信息\n"
        "/weather <城市> (天气) - 查询天气 (例如: /天气 北京)\n"
        "/add_rss <url> (订阅) - 订阅 RSS 源\n"
        "/rss list (订阅列表) - 查看已订阅列表\n"
        "/rss del <id> (取消订阅 <id>) - 取消订阅\n"
        "/rss_digest (今日摘要) - 生成今日 RSS 摘要\n"
        "/remind add <HH:MM> <内容> (提醒) - 添加提醒\n"
        "/remind list - 查看提醒列表\n"
        "/summary (总结) - 手动总结群聊消息 (需 >50 条)\n"
        "/水群榜 (聊天榜) - 查看群聊活跃度排名\n"
        "------------------------\n"
        "💡 提示: 所有指令均支持中英文别名"
    )
    
    # Use smart forwarding
    from src.utils.message_forwarder import send_message_smart
    threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
    
    try:
        bot = get_bot()
        await send_message_smart(bot, help_text, event, threshold)
    except Exception:
        await help_cmd.send(help_text)
        
    await help_cmd.finish()
