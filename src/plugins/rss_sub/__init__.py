import json
import os
import asyncio
import feedparser
from nonebot import on_command, require, get_bot
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

# File to store subscriptions
SUBS_FILE = "data/rss_subs.json"  # Store in data directory for persistence

def load_subs():
    if not os.path.exists(SUBS_FILE):
        return {}
    with open(SUBS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_subs(subs):
    with open(SUBS_FILE, "w", encoding="utf-8") as f:
        json.dump(subs, f, indent=4, ensure_ascii=False)

# Commands
add_rss = on_command("add_rss", aliases={"订阅"}, priority=5)

@add_rss.handle()
async def handle_add_rss(event: Union[GroupMessageEvent, PrivateMessageEvent], args: Message = CommandArg()):
    url = args.extract_plain_text().strip()
    if not url:
        await add_rss.finish("请输入 RSS 链接。")
        return

    subs = load_subs()
    
    # Determine subscriber info
    subscriber = {}
    if isinstance(event, GroupMessageEvent):
        subscriber = {"type": "group", "id": event.group_id}
    elif isinstance(event, PrivateMessageEvent):
        subscriber = {"type": "private", "id": event.user_id}
    
    # Check if feed exists
    if url not in subs:
        # New feed
        feed = feedparser.parse(url)
        if feed.bozo:
            await add_rss.finish("无效的 RSS 源。")
            return
        
        title = feed.feed.get("title", "Unknown Feed")
        
        # Initialize last_entry_id with the most recent entry to avoid pushing all history
        latest_entry_id = None
        if feed.entries:
            latest_entry_id = feed.entries[0].get("id", feed.entries[0].get("link"))
        
        subs[url] = {
            "title": title,
            "last_entry_id": latest_entry_id,  # Set to latest entry, not None
            "subscribers": [subscriber]
        }
        msg = f"成功订阅 {title}！已忽略历史消息，仅推送新内容。"
    else:
        # Existing feed, check if already subscribed
        if subscriber in subs[url]["subscribers"]:
            await add_rss.finish("你已经订阅过这个源了。")
            return
        
        subs[url]["subscribers"].append(subscriber)
        msg = f"成功订阅 {subs[url]['title']}！"

    save_subs(subs)
    await add_rss.finish(msg)

# Scheduled Task
async def check_rss():
    logger.info("Checking RSS feeds...")
    subs = load_subs()
    bot = get_bot()
    
    for url, data in subs.items():
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                continue
            
            new_entries = []
            last_id = data.get("last_entry_id")
            
            # Collect all new entries (up to 20 to avoid excessive processing)
            for entry in feed.entries:
                entry_id = entry.get("id", entry.get("link"))
                if entry_id == last_id:
                    break
                new_entries.append(entry)
                
                # Hard limit: max 20 entries to analyze
                if len(new_entries) >= 20:
                    logger.info(f"RSS {data['title']}: 达到收集上限(20条)")
                    break
            
            if new_entries:
                # Update last_id
                data["last_entry_id"] = new_entries[0].get("id", new_entries[0].get("link"))
                save_subs(subs)
                
                # Smart filtering: if more than 5 entries, use AI to select top 5 by importance
                entries_to_push = new_entries
                if len(new_entries) > 5:
                    logger.info(f"RSS {data['title']}: 检测到{len(new_entries)}条新内容，使用AI筛选...")
                    entries_to_push = await select_top_entries(new_entries, data['title'])
                
                # Build a single message with all entries from this source
                entry_count = len(entries_to_push)
                msg_lines = [f"📢 {data['title']} 更新 ({entry_count}条)：\n"]
                
                for idx, entry in enumerate(reversed(entries_to_push), 1):
                    msg_lines.append(f"{idx}. {entry.title}")
                    msg_lines.append(f"   {entry.link}")
                    if idx < entry_count:  # Add separator between entries
                        msg_lines.append("")
                
                msg = "\n".join(msg_lines)
                
                # Push the combined message to all subscribers
                subscribers = data.get("subscribers", [])
                for sub in subscribers:
                    try:
                        # Check length for smart forwarding
                        threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
                        
                        if len(msg) > threshold:
                            from src.utils.message_forwarder import send_group_forward_message, send_private_forward_message, split_text_into_paragraphs
                            paragraphs = split_text_into_paragraphs(msg)
                            
                            if sub["type"] == "group":
                                await send_group_forward_message(bot, int(sub["id"]), paragraphs)
                            elif sub["type"] == "private":
                                await send_private_forward_message(bot, int(sub["id"]), paragraphs)
                        else:
                            if sub["type"] == "group":
                                await bot.send_group_msg(group_id=int(sub["id"]), message=msg)
                            elif sub["type"] == "private":
                                await bot.send_private_msg(user_id=int(sub["id"]), message=msg)
                    except Exception as e:
                        logger.error(f"Failed to send RSS to {sub}: {e}")
                        
                logger.info(f"Pushed {entry_count} RSS items from {data['title']}")
                    
        except Exception as e:
            logger.error(f"Error checking RSS {url}: {e}")

async def select_top_entries(entries, feed_title):
    """
    Use AI to select the top 5 most important/newsworthy entries from a list.
    Falls back to latest 5 if AI fails.
    """
    try:
        from src.utils.openai_client import openai_client
        
        # Build prompt with all entry titles
        entries_text = "\n".join([
            f"{idx+1}. {entry.title}" 
            for idx, entry in enumerate(entries)
        ])
        
        prompt = (
            f"你是新闻编辑。以下是{feed_title}的{len(entries)}条新闻标题。\n"
            f"请选出最重要、最有新闻价值的5条（按重要性排序）。\n"
            f"只需返回选中的新闻序号，用逗号分隔，例如：3,7,1,12,5\n\n"
            f"{entries_text}"
        )
        
        # Use Pro model for highest quality filtering
        response = await openai_client.generate_content(
            'auto', 
            prompt, 
            task_type='summary',
            auto_select=False
        )
        
        # Parse AI response to get selected indices
        selected_indices = []
        for num in response.strip().split(','):
            try:
                idx = int(num.strip()) - 1  # Convert to 0-indexed
                if 0 <= idx < len(entries):
                    selected_indices.append(idx)
            except ValueError:
                continue
        
        # If AI successfully selected entries, return them
        if selected_indices:
            selected = [entries[i] for i in selected_indices[:5]]
            logger.info(f"AI筛选成功：从{len(entries)}条中选出{len(selected)}条")
            return selected
        else:
            logger.warning(f"AI返回的索引无效，使用默认策略")
        
    except ValueError as e:
        # Handle openai_client specific errors (finish_reason issues)
        logger.warning(f"AI筛选失败 (内容问题): {e}，使用默认策略")
    except Exception as e:
        # Handle all other unexpected errors
        logger.warning(f"AI筛选失败 ({type(e).__name__}): {e}，使用默认策略")
    
    # Fallback: return latest 5
    logger.info(f"使用默认策略：选择最新的5条")
    return entries[:5]

# Schedule the check every 90 minutes (low-frequency mode)
scheduler.add_job(check_rss, "interval", minutes=90)

# RSS Digest Feature
rss_digest = on_command("rss_digest", aliases={"今日摘要", "RSS摘要"}, priority=5)

@rss_digest.handle()
async def handle_rss_digest(event: Union[GroupMessageEvent, PrivateMessageEvent], args: Message = CommandArg()):
    # /rss_digest HH:MM (Set daily digest time)
    # For now, let's just trigger it immediately for testing if no time provided, 
    # or save the schedule if time provided.
    
    args_text = args.extract_plain_text().strip()
    
    # Determine subscriber info
    target_id = str(event.user_id) if isinstance(event, PrivateMessageEvent) else str(event.group_id)
    target_type = "private" if isinstance(event, PrivateMessageEvent) else "group"
    
    subs = load_subs()
    
    # Collect recent entries from subscribed feeds
    recent_entries = []
    subscriber_signature = {"type": target_type, "id": int(target_id)}
    
    for url, data in subs.items():
        if subscriber_signature in data.get("subscribers", []):
            # Fetch feed again to get latest content (or use cached if we had it, but we don't cache content)
            # This might be slow if many feeds.
            try:
                feed = feedparser.parse(url)
                # Get entries from last 24h (simplified: just take top 5 from each feed for now)
                for entry in feed.entries[:5]:
                    recent_entries.append(f"- [{data['title']}] {entry.title}: {entry.link}")
            except Exception:
                pass
    
    if not recent_entries:
        await rss_digest.finish("暂无订阅或无近期更新。")
        return

    await rss_digest.send("正在生成今日摘要，请稍候...")
    
    # Limit to top 20 items to avoid token limits (reduced from 50)
    content_text = "\n".join(recent_entries[:20])
    
    prompt = (
        "你是一个研究助手。以下是用户 RSS 订阅的近期文章列表。"
        "请挑选出最重要的 5 篇文章。"
        "对于每一篇，提供标题、一句话的中文重要性总结，以及链接。"
        "请使用带编号的列表格式输出。\n\n"
        f"{content_text}"
    )
    
    
    from src.utils.openai_client import openai_client
    from src.utils.text_formatter import markdown_to_plain_text
    
    # Variables to store results
    digest = None
    error_message = None
    
    try:
        digest = await openai_client.generate_content('auto', prompt, task_type='summary')
        # Convert Markdown to plain text for QQ compatibility
        digest = markdown_to_plain_text(digest)
    except ValueError as e:
        # Handle specific errors from openai_client
        error_msg = str(e)
        if "安全过滤器" in error_msg or "SAFETY" in error_msg:
            error_message = "⚠️ 生成摘要失败：RSS内容包含敏感信息被过滤\n建议：请检查订阅源内容"
        elif "token" in error_msg.lower() or "MAX_TOKENS" in error_msg:
            error_message = "⚠️ 生成摘要失败：内容过长\n建议：减少订阅源数量或稍后重试"
        elif "空响应" in error_msg:
            error_message = "⚠️ 生成摘要失败：API返回空响应\n建议：请稍后重试"
        else:
            error_message = f"❌ 生成摘要失败：{error_msg}"
    except Exception as e:
        # Handle unexpected errors
        error_message = f"❌ 生成摘要失败：{type(e).__name__}: {str(e)}\n建议：请检查日志或稍后重试"
    
    # Now send the response (outside of the try-except to avoid catching FinishedException)
    # Now send the response (outside of the try-except to avoid catching FinishedException)
    if digest:
        msg = f"📰 今日 RSS 摘要：\n{digest}"
        
        # Use smart forwarding
        from src.utils.message_forwarder import send_message_smart
        threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
        
        try:
            bot = get_bot()
            await send_message_smart(bot, msg, event, threshold)
        except Exception as e:
            logger.error(f"Smart send failed: {e}")
            await rss_digest.send(msg)
            
        await rss_digest.finish()
    else:
        await rss_digest.finish(error_message)


# RSS List Command
rss_list = on_command("rss", aliases={"订阅列表"}, priority=5)
rss_delete = on_command("取消订阅", priority=5)
rss_show_list = on_command("订阅列表", priority=5)

async def perform_list(matcher, event):
    """
    执行显示订阅列表逻辑
    """
    # Determine subscriber info
    target_id = str(event.user_id) if isinstance(event, PrivateMessageEvent) else str(event.group_id)
    target_type = "private" if isinstance(event, PrivateMessageEvent) else "group"
    subscriber_signature = {"type": target_type, "id": int(target_id)}
    
    subs = load_subs()
    
    # Filter subs for this user/group
    user_subs = []
    for url, data in subs.items():
        if subscriber_signature in data.get("subscribers", []):
            user_subs.append((url, data["title"]))
    
    if not user_subs:
        await matcher.finish("当前暂无订阅。")
        return
        
    msg = "📋 已订阅列表：\n"
    for idx, (url, title) in enumerate(user_subs):
        msg += f"{idx + 1}. {title}\n   {url}\n"
        
    # Use smart forwarding
    from src.utils.message_forwarder import send_message_smart
    threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
    
    try:
        bot = get_bot()
        await send_message_smart(bot, msg, event, threshold)
    except Exception:
        await matcher.send(msg)
        
    await matcher.finish()

async def perform_unsubscribe(matcher, event, target):
    """
    执行取消订阅逻辑
    """
    # Determine subscriber info
    target_id = str(event.user_id) if isinstance(event, PrivateMessageEvent) else str(event.group_id)
    target_type = "private" if isinstance(event, PrivateMessageEvent) else "group"
    subscriber_signature = {"type": target_type, "id": int(target_id)}
    
    subs = load_subs()
    
    # Filter subs for this user/group
    user_subs = []
    for url, data in subs.items():
        if subscriber_signature in data.get("subscribers", []):
            user_subs.append((url, data["title"]))
    
    url_to_remove = None
    
    # Try to parse as index
    if target.isdigit():
        idx = int(target) - 1
        if 0 <= idx < len(user_subs):
            url_to_remove = user_subs[idx][0]
    else:
        # Try to match URL
        if target in subs:
            url_to_remove = target
    
    if not url_to_remove:
        await matcher.finish("未找到该订阅。")
        return
        
    # Remove subscriber
    subs[url_to_remove]["subscribers"].remove(subscriber_signature)
    
    # If no subscribers left, remove feed? 
    if not subs[url_to_remove]["subscribers"]:
        del subs[url_to_remove]
        
    save_subs(subs)
    await matcher.finish(f"成功取消订阅 {url_to_remove}。")


@rss_delete.handle()
async def handle_rss_delete(event: Union[GroupMessageEvent, PrivateMessageEvent], args: Message = CommandArg()):
    target = args.extract_plain_text().strip()
    if not target:
        await rss_delete.finish("用法：/取消订阅 <链接或序号>")
        return
    
    await perform_unsubscribe(rss_delete, event, target)


@rss_show_list.handle()
async def handle_rss_show_list(event: Union[GroupMessageEvent, PrivateMessageEvent]):
    await perform_list(rss_show_list, event)


@rss_list.handle()
async def handle_rss_list(event: Union[GroupMessageEvent, PrivateMessageEvent], args: Message = CommandArg()):
    # Usage: /rss list
    #        /rss del <url_or_index>
    
    args_text = args.extract_plain_text().strip().split()
    if not args_text:
        await rss_list.finish("用法：/rss list 或 /rss del <链接或序号>")
        return
        
    action = args_text[0].lower()
    
    if action == "list":
        await perform_list(rss_list, event)
        
    elif action == "del":
        if len(args_text) < 2:
            await rss_list.finish("用法：/rss del <链接或序号>")
            return
            
        target = args_text[1]
        await perform_unsubscribe(rss_list, event, target)
    
    else:
        await rss_list.finish("未知操作。请使用 list 或 del。")
