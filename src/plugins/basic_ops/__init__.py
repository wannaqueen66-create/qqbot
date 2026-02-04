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
    help_text = """🤖 QQBot 帮助菜单:
------------------------
基础：
  /ping（在吗）- 检查机器人是否在线
  /help（帮助/菜单）- 显示此帮助

聊天：
  群聊：必须 @机器人 才回复
  私聊：直接发消息即可
  /clear（清空记忆）- 清空个人上下文（群里也会同步清空你在本群的短期上下文）
  /memory（记忆统计）- 查看记忆统计

常用功能：
  /weather <城市>（天气）- 查询天气，例如：/天气 北京
  /add_rss <url>（订阅）- 订阅 RSS
  /rss list（订阅列表）- 查看订阅
  /rss del <id>（取消订阅）- 取消订阅
  /rss_digest（今日摘要）- 生成 RSS 摘要
  /remind add <HH:MM> <内容>（提醒）- 添加提醒
  /remind list - 查看提醒
  /summary（总结）- 手动总结群聊
  /水群榜（聊天榜/发言榜）- 群聊活跃度排名

图片：
  /draw <描述>（画/生成图片/画图）- 生图（可能有频率/额度限制）

管理员：
  /status - 查看运行/路由配置（仅管理员私聊）
  /task - 管理定时任务（管理员）
  /aclear <QQ号> [群号] - 清空指定用户个人记忆（管理员）
  /gclear [群号] - 清空某群短期上下文（管理员）
  /aclear <QQ号> [群号] - 清空指定用户个人记忆（管理员）
------------------------
💡 提示：指令支持中英文别名
"""

    # Use smart forwarding
    from src.utils.message_forwarder import send_message_smart
    threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
    
    try:
        bot = get_bot()
        await send_message_smart(bot, help_text, event, threshold)
    except Exception:
        await help_cmd.send(help_text)
        
    await help_cmd.finish()

