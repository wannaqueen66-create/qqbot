from nonebot import on_message, on_command, get_bot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Bot
from nonebot.log import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import os
import aiohttp
import json

from nonebot import get_driver

# Initialize Scheduler
scheduler = AsyncIOScheduler()
driver = get_driver()

@driver.on_startup
async def start_scheduler():
    if not scheduler.running:
        scheduler.start()

# In-memory chat history: {group_id: [(timestamp, sender, message)]}
chat_history = {}
# Track last manual summary time: {group_id: timestamp}
last_manual_summary_time = {}

# Commands
manual_summary_cmd = on_command("summary", aliases={"总结"}, priority=5)

@manual_summary_cmd.handle()
async def handle_manual_summary(event: GroupMessageEvent):
    group_id = event.group_id
    
    # Get last summary time or default to very old time
    last_time = last_manual_summary_time.get(group_id, datetime.min)
    
    # Get messages from database since last summary
    from src.utils.database import db
    messages = db.get_group_messages_since(group_id, last_time)
    
    if len(messages) < 50:
        await manual_summary_cmd.finish(f"消息太少，无法生成总结 (当前: {len(messages)}/50)。")
        return

    # Generate summary
    await manual_summary_cmd.send("正在生成总结...")
    summary = await generate_summary(messages)
    
    # Update last summary time
    last_manual_summary_time[group_id] = datetime.now()
    
    # Save to long-term memory (Tier 3)
    from src.utils.conversation_memory import conversation_memory
    from src.utils.text_formatter import markdown_to_plain_text
    
    # Convert Markdown to plain text for QQ compatibility
    summary = markdown_to_plain_text(summary)
    conversation_memory.add_group_summary(str(group_id), f"手动总结: {summary}")
    
    msg = f"📝 群聊总结：\n{summary}"
    
    # Use smart forwarding
    from src.utils.message_forwarder import send_message_smart
    threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
    
    try:
        bot = get_bot()
        await send_message_smart(bot, msg, event, threshold)
    except Exception:
        await manual_summary_cmd.send(msg)
        
    await manual_summary_cmd.finish()

# Message Recorder
recorder = on_message(priority=10, block=False)

@recorder.handle()
async def record_message(event: GroupMessageEvent):
    group_id = event.group_id
    # 优先使用群名片(card)，其次是QQ昵称(nickname)，最后是QQ号
    sender = event.sender.card or event.sender.nickname or str(event.user_id)
    content = event.get_plaintext()
    
    # Save to database
    from src.utils.database import db
    db.add_group_message(group_id, sender, content)

# Gemini API Summarization
async def generate_summary(messages):
    from src.utils.openai_client import openai_client
    
    if not messages:
        return "没有消息可总结。"

    # Format messages for prompt
    chat_text = "\n".join([f"[{m['time'].strftime('%H:%M')}] {m['sender']}: {m['content']}" for m in messages])
    
    prompt = (
        "请总结以下聊天记录。"
        "关注关键话题、决定和有趣的讨论。"
        "输出格式为带有标题的简洁要点列表。\n\n"
        f"{chat_text}"
    )

    return await openai_client.generate_content('auto', prompt, task_type='summary')

# Scheduled Summary Task
async def push_summary(period_name):
    logger.info(f"Generating {period_name} summary...")
    
    target_groups = json.loads(os.getenv("TARGET_GROUPS", "[]"))
    target_groups = [int(gid) for gid in target_groups]
    
    bot = get_bot()
    from src.utils.database import db
    
    # Iterate over target groups
    for group_id in target_groups:
        try:
            # Get messages from last 6 hours from database
            messages = db.get_group_messages(group_id, hours=6, limit=500)
            
            if not messages or len(messages) < 10:
                continue
                
            summary = await generate_summary(messages)
            
            # Convert Markdown to plain text for QQ compatibility
            from src.utils.text_formatter import markdown_to_plain_text
            summary = markdown_to_plain_text(summary)
            
            msg = f"📝 {period_name} 总结：\n{summary}"
            
            # Save to long-term memory (Tier 3)
            from src.utils.conversation_memory import conversation_memory
            conversation_memory.add_group_summary(str(group_id), f"{period_name}: {summary}")
            
            # Check length for smart forwarding
            threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
            
            if len(msg) > threshold:
                from src.utils.message_forwarder import send_group_forward_message, split_text_into_paragraphs
                paragraphs = split_text_into_paragraphs(msg)
                await send_group_forward_message(bot, group_id, paragraphs)
            else:
                await bot.send_group_msg(group_id=group_id, message=msg)
                
            logger.info(f"Sent summary to group {group_id} and saved to long-term memory")
        except Exception as e:
            logger.error(f"Failed to generate/send summary for group {group_id}: {e}")

# Schedule summaries
scheduler.add_job(push_summary, "cron", hour=8, args=["早间"])
scheduler.add_job(push_summary, "cron", hour=11, args=["午前"])
scheduler.add_job(push_summary, "cron", hour=14, args=["午后"])
scheduler.add_job(push_summary, "cron", hour=17, args=["傍晚"])
scheduler.add_job(push_summary, "cron", hour=20, args=["晚间"])
scheduler.add_job(push_summary, "cron", hour=23, args=["夜间"])
