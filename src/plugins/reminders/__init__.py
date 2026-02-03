import json
import os
from datetime import datetime
from nonebot import on_command, require, get_bot
from src.utils.safe_bot import safe_get_bot
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.params import CommandArg
from nonebot.log import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Union

from nonebot import get_driver

# Initialize Scheduler
scheduler = AsyncIOScheduler()
driver = get_driver()

@driver.on_startup
async def start_scheduler():
    if not scheduler.running:
        scheduler.start()

REMINDERS_FILE = "reminders.json"

def load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return {}
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reminders(data):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# Commands
remind = on_command("remind", aliases={"提醒"}, priority=5)

@remind.handle()
async def handle_remind(event: Union[GroupMessageEvent, PrivateMessageEvent], args: Message = CommandArg()):
    # Format: /remind add HH:MM content
    #         /remind list
    #         /remind del ID
    
    args_text = args.extract_plain_text().strip().split()
    if not args_text:
        await remind.finish("用法：/remind add <时间> <内容> | list | del <ID>")
        return

    action = args_text[0].lower()
    
    # Determine user/group ID
    target_id = str(event.user_id) if isinstance(event, PrivateMessageEvent) else str(event.group_id)
    target_type = "private" if isinstance(event, PrivateMessageEvent) else "group"
    
    data = load_reminders()
    if target_id not in data:
        data[target_id] = {"type": target_type, "items": []}

    if action == "add":
        if len(args_text) < 3:
            await remind.finish("用法：/remind add <时间> <内容>")
            return
        
        time_str = args_text[1]
        content = " ".join(args_text[2:])
        
        # Validate time
        try:
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            await remind.finish("时间格式错误。请使用 HH:MM (24小时制)。")
            return
            
        # Generate ID (simple index based)
        new_id = len(data[target_id]["items"]) + 1
        data[target_id]["items"].append({
            "id": new_id,
            "time": time_str,
            "content": content
        })
        save_reminders(data)
        save_reminders(data)
        await remind.finish(f"✅ 提醒已添加！ID: {new_id}, 时间: {time_str}")

    elif action == "list":
        items = data[target_id]["items"]
        if not items:
            await remind.finish("暂无提醒。")
            return
        
        msg = "📅 提醒列表：\n" + "\n".join([f"[{i['id']}] {i['time']} - {i['content']}" for i in items])
        await remind.finish(msg)

    elif action == "del":
        if len(args_text) < 2:
            await remind.finish("用法：/remind del <ID>")
            return
        
        try:
            del_id = int(args_text[1])
        except ValueError:
            await remind.finish("无效的 ID。")
            return
            
        items = data[target_id]["items"]
        new_items = [i for i in items if i["id"] != del_id]
        
        if len(items) == len(new_items):
            await remind.finish("未找到该 ID 的提醒。")
            return
            
        # Re-index
        for idx, item in enumerate(new_items):
            item["id"] = idx + 1
            
        data[target_id]["items"] = new_items
        save_reminders(data)
        await remind.finish("提醒已删除。")
    
    else:
        await remind.finish("未知操作。请使用 add, list 或 del。")

# Scheduled Check
async def check_reminders():
    now = datetime.now().strftime("%H:%M")
    data = load_reminders()
    bot = safe_get_bot()
    if not bot:
        return
    
    for target_id, info in data.items():
        target_type = info["type"]
        for item in info["items"]:
            if item["time"] == now:
                msg = f"⏰ 提醒：{item['content']}"
                try:
                    if target_type == "group":
                        await bot.send_group_msg(group_id=int(target_id), message=msg)
                    else:
                        await bot.send_private_msg(user_id=int(target_id), message=msg)
                    logger.info(f"Sent reminder to {target_id}: {item['content']}")
                except Exception as e:
                    logger.error(f"Failed to send reminder to {target_id}: {e}")

# Check every minute
scheduler.add_job(check_reminders, "cron", second=0)
