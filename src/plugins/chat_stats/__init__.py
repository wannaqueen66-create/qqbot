"""
水群榜插件
统计群成员发言数量并生成排行榜
"""
from nonebot import on_message, on_command, get_bot, require
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.typing import T_State
from nonebot.log import logger
from datetime import datetime

# 导入统计管理器
from .stats_manager import chat_stats_manager

# 导入调度器
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from nonebot import get_driver

scheduler = AsyncIOScheduler()
driver = get_driver()

@driver.on_startup
async def start_scheduler():
    if not scheduler.running:
        scheduler.start()

# 消息监听器（优先级较低，不拦截消息）
message_recorder = on_message(priority=99, block=False)

# 命令处理器
ranking_cmd = on_command("水群榜", aliases={"聊天榜", "发言榜"}, priority=5)


@message_recorder.handle()
async def record_group_message(bot: Bot, event: GroupMessageEvent):
    """
    记录群消息
    """
    try:
        # 只记录群消息
        if not isinstance(event, GroupMessageEvent):
            return
        
        # 提取消息文本
        message_text = event.get_plaintext().strip()
        
        # 记录消息
        chat_stats_manager.record_message(
            group_id=event.group_id,
            user_id=event.user_id,
            nickname=event.sender.nickname or event.sender.card or str(event.user_id),
            message_text=message_text  # 传入消息文本
        )
        
    except Exception as e:
        logger.error(f"Failed to record message: {e}")


@ranking_cmd.handle()
async def show_ranking(bot: Bot, event: GroupMessageEvent):
    """
    显示水群榜
    """
    try:
        group_id = event.group_id
        
        # 获取排行榜
        ranking = chat_stats_manager.get_ranking(group_id)
        
        if not ranking:
            await ranking_cmd.finish("今天还没有人发言哦~")
        
        # 获取群统计信息
        stats = chat_stats_manager.get_group_stats(group_id)
        last_push = chat_stats_manager.get_last_push_time(group_id)
        
        # 格式化消息
        message = format_ranking_message(ranking, stats, last_push, is_daily=False)
        
        # 生成AI点评（针对水王）- 独立的错误处理，避免影响主功能
        try:
            if ranking:
                top_user = ranking[0]
                recent_msgs = chat_stats_manager.get_user_recent_messages(
                    group_id=group_id,
                    user_id=top_user["user_id"]
                )
                
                if recent_msgs:
                    ai_comment = await generate_ai_commentary(
                        nickname=top_user["nickname"],
                        recent_messages=recent_msgs
                    )
                    message += f"\n\n💬 AI锐评：{ai_comment}"
        except Exception as e:
            logger.warning(f"Failed to generate AI commentary (not critical): {e}")
            # AI点评失败不影响主功能，继续显示排行榜
        
        await ranking_cmd.finish(message)
        
    except Exception as e:
        logger.error(f"Failed to show ranking: {e}")
        await ranking_cmd.finish("获取排行榜失败，请稍后重试")


def format_ranking_message(
    ranking: list,
    stats: dict,
    last_push: str = None,
    is_daily: bool = False
) -> str:
    """
    格式化排行榜消息
    
    Args:
        ranking: 排行榜数据
        stats: 群统计信息
        last_push: 上次推送时间
        is_daily: 是否为每日推送
        
    Returns:
        str: 格式化后的消息
    """
    now = datetime.now()
    today_date = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%H:%M')
    
    # 标题和时间范围
    if is_daily:
        title = "🏆 今日水群榜 🏆"
        # 每日推送在23:00，统计的是前一天23:00到今天23:00的24小时
        yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        time_range = f"📅 统计时间：{yesterday} 23:00 ~ {today_date} 23:00"
    else:
        title = "🏆 水群榜 🏆"
        if last_push:
            # 如果有上次推送时间，显示从上次推送到现在
            time_range = f"📅 统计时间：{last_push} 至 {today_date} {current_time}"
        else:
            # 如果没有上次推送时间，显示今日00:00到现在
            time_range = f"📅 统计时间：{today_date} 00:00 至 {current_time}"
    
    lines = [
        title,
        time_range,
        ""
    ]
    
    # 排行榜
    medals = ["👑", "🥈", "🥉"]
    numbers = ["4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for idx, user in enumerate(ranking):
        rank = idx + 1
        nickname = user["nickname"]
        count = user["count"]
        
        # 排名图标
        if rank == 1:
            prefix = f"{medals[0]} 水王"
        elif rank == 2:
            prefix = f"{medals[1]} 亚军"
        elif rank == 3:
            prefix = f"{medals[2]} 季军"
        elif rank <= 10:
            prefix = numbers[rank - 4]
        else:
            prefix = f"{rank}."
        
        # 特殊称号
        if rank == 1:
            suffix = " 💦"
        else:
            suffix = ""
        
        lines.append(f"{prefix} {nickname} ({count}条){suffix}")
    
    # 统计信息
    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━",
        f"📊 群总消息：{stats['total_messages']}条",
        f"👥 活跃人数：{stats['active_users']}人"
    ])
    
    return "\n".join(lines)


async def generate_ai_commentary(nickname: str, recent_messages: list) -> str:
    """
    生成AI锐评
    
    Args:
        nickname: 水王昵称
        recent_messages: 最近的消息列表
        
    Returns:
        str: AI生成的点评
    """
    try:
        from src.utils.openai_client import openai_client
        
        # 构建提示词
        messages_text = "\n".join([
            f"[{msg['time']}] {msg['text']}"
            for msg in recent_messages
        ])
        
        prompt = f"""你是一个幽默风趣的群聊观察员。请针对今天的"水王"（发言最多的人）生成一句简短有趣的点评或吐槽。

水王昵称：{nickname}
TA最近的几条发言：
{messages_text}

要求：
1. 一句话，不超过30个字
2. 要幽默、轻松、有趣
3. 可以调侃但要善意，不要过分
4. 可以结合发言内容特点
5. 直接输出点评内容，不要前缀

示例风格：
- "今天{nickname}话特别多，是吃了话痨药吗？😄"
- "恭喜{nickname}喜提水王，键盘都要冒烟了吧！"
- "看{nickname}今天这发言量，是不是有什么开心事啊~"
"""
        
        # 调用AI生成
        commentary = await openai_client.generate_content(
            model='auto',  # 使用Flash模型，快速且便宜
            prompt=prompt,
            task_type='chat'
        )
        
        # 清理格式
        commentary = commentary.strip().strip('"').strip("'")
        
        # 长度限制
        if len(commentary) > 50:
            commentary = commentary[:47] + "..."
        
        return commentary
        
    except Exception as e:
        logger.error(f"Failed to generate AI commentary: {e}")
        # 返回默认点评
        return f"恭喜 {nickname} 荣登水王宝座！🎉"


@scheduler.scheduled_job("cron", hour=23, minute=0, id="daily_ranking_push")
async def daily_ranking_push():
    """
    每天23点推送排行榜
    """
    try:
        logger.info("Starting daily ranking push...")
        
        # 获取所有活跃群
        active_groups = chat_stats_manager.get_all_active_groups()
        
        if not active_groups:
            logger.info("No active groups found")
            return
        
        # 获取bot实例
        try:
            bot = get_bot()
        except Exception as e:
            logger.error(f"Failed to get bot instance: {e}")
            return
        
        # 遍历所有群
        for group_id in active_groups:
            try:
                # 获取排行榜
                ranking = chat_stats_manager.get_ranking(group_id)
                
                if not ranking:
                    logger.info(f"No ranking data for group {group_id}")
                    continue
                
                # 获取群统计
                stats = chat_stats_manager.get_group_stats(group_id)
                
                # 格式化消息
                message = format_ranking_message(ranking, stats, is_daily=True)
                
                # 生成AI点评（针对水王）
                if ranking:
                    top_user = ranking[0]
                    recent_msgs = chat_stats_manager.get_user_recent_messages(
                        group_id=group_id,
                        user_id=top_user["user_id"]
                    )
                    
                    if recent_msgs:
                        ai_comment = await generate_ai_commentary(
                            nickname=top_user["nickname"],
                            recent_messages=recent_msgs
                        )
                        message += f"\n\n💬 AI锐评：{ai_comment}"
                
                # 发送消息
                await bot.send_group_msg(
                    group_id=int(group_id),
                    message=message
                )
                
                # 更新推送时间
                chat_stats_manager.update_push_time(group_id)
                
                logger.info(f"Sent daily ranking to group {group_id}")
                
                # 短暂延迟，避免发送过快
                import asyncio
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to push ranking to group {group_id}: {e}")
        
        # 强制保存数据
        chat_stats_manager.force_save()
        
        logger.info("Daily ranking push completed")
        
    except Exception as e:
        logger.error(f"Daily ranking push error: {e}")


# 插件加载时的日志
logger.info("Chat stats plugin loaded")
