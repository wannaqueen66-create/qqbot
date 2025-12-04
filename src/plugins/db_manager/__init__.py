from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
from typing import Union
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from nonebot import get_driver

# Initialize Scheduler
scheduler = AsyncIOScheduler()
driver = get_driver()

@driver.on_startup
async def start_scheduler():
    if not scheduler.running:
        scheduler.start()
    
    # Schedule daily database cleanup at 3 AM
    from src.utils.database import db
    scheduler.add_job(db.cleanup_old_data, "cron", hour=3)
    logger.info("Database cleanup scheduled for 3 AM daily")

# Database stats command
db_stats_cmd = on_command("db", aliases={"数据库"}, priority=5)

@db_stats_cmd.handle()
async def handle_db_stats(event: Union[GroupMessageEvent, PrivateMessageEvent]):
    from src.utils.database import db
    
    stats = db.get_stats()
    
    msg = (
        f"📊 数据库统计：\n"
        f"👥 活跃用户数：{stats['active_users']}\n"
        f"💬 对话消息数：{stats['total_conversations']}\n"
        f"🏘️ 活跃群数：{stats['active_groups']}\n"
        f"📝 群消息数：{stats['total_group_messages']}\n"
        f"📋 总结数：{stats['total_summaries']}\n"
        f"💾 数据库大小：{stats['db_size_mb']} MB"
    )
    
    await db_stats_cmd.finish(msg)
