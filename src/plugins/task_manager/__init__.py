import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional, Dict

from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.utils.auth import admin_user_ids
from src.utils.safe_bot import safe_get_bot
from src.utils.message_forwarder import send_group_forward_message, split_text_into_paragraphs


driver = get_driver()
scheduler = AsyncIOScheduler()


def _is_admin(event) -> bool:
    uid = int(getattr(event, "user_id", 0) or 0)
    return uid in admin_user_ids()


def _db_path() -> str:
    # reuse qqbot sqlite
    return os.getenv("QQBOT_DB_FILE", "data/qqbot_data.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            task_type TEXT NOT NULL,
            schedule_type TEXT NOT NULL,
            schedule_value TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            params TEXT,
            enabled INTEGER DEFAULT 1,
            last_run DATETIME,
            last_error TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def _parse_target(raw: str, event: GroupMessageEvent | PrivateMessageEvent) -> tuple[str, str]:
    # group:836571848 / private:123 / or bare number = group if in group else private
    r = (raw or "").strip()
    if not r:
        if isinstance(event, GroupMessageEvent):
            return ("group", str(event.group_id))
        return ("private", str(event.user_id))
    if r.startswith("group:"):
        return ("group", r.split(":", 1)[1])
    if r.startswith("private:"):
        return ("private", r.split(":", 1)[1])
    # bare
    if isinstance(event, GroupMessageEvent):
        return ("group", r)
    return ("private", r)


def _schedule_to_trigger(schedule_type: str, schedule_value: str) -> CronTrigger:
    st = schedule_type
    sv = schedule_value
    tz = os.getenv("TZ", "Asia/Shanghai")

    if st == "daily":
        # HH:MM
        hh, mm = sv.split(":", 1)
        return CronTrigger(hour=int(hh), minute=int(mm), timezone=tz)
    if st == "hourly":
        # every N hours, at minute 0
        n = int(sv)
        return CronTrigger(minute=0, hour=f"*/{n}", timezone=tz)
    if st == "cron":
        # 5-field cron
        parts = sv.strip().split()
        if len(parts) != 5:
            raise ValueError("cron 表达式需要 5 段，如: */30 * * * *")
        minute, hour, day, month, dow = parts
        return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=dow, timezone=tz)
    raise ValueError("schedule_type must be daily/hourly/cron")


def _smart_send(target_type: str, target_id: str, text: str):
    bot = safe_get_bot()
    if not bot:
        return
    threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
    if target_type == "group":
        gid = int(target_id)
        if len(text) > threshold:
            paragraphs = split_text_into_paragraphs(text)
            return bot.call_api("send_group_forward_msg", group_id=gid, messages=[
                {"type": "node", "data": {"name": os.getenv("BOT_NICKNAME", "AI 助手"), "uin": str(bot.self_id), "content": p}} for p in paragraphs
            ])
        return bot.send_group_msg(group_id=gid, message=text)
    else:
        uid = int(target_id)
        # private forwarding also exists; keep simple
        return bot.send_private_msg(user_id=uid, message=text)


async def _run_task(task: Dict[str, Any]):
    task_type = task["task_type"]
    target_type = task["target_type"]
    target_id = task["target_id"]
    params = {}
    try:
        params = json.loads(task.get("params") or "{}") if task.get("params") else {}
    except Exception:
        params = {}

    try:
        if task_type == "rss_digest":
            await _task_rss_digest(target_type, target_id, params)
        elif task_type == "group_summary":
            await _task_group_summary(target_type, target_id, params)
        elif task_type == "db_cleanup":
            await _task_db_cleanup(target_type, target_id, params)
        else:
            await _smart_send(target_type, target_id, f"⚠️ 未知任务类型：{task_type}")

        _update_task_run(task["id"], None)
    except Exception as e:
        logger.error(f"[task] run failed id={task['id']}: {type(e).__name__}: {e}")
        _update_task_run(task["id"], f"{type(e).__name__}: {e}")


def _update_task_run(task_id: int, err: Optional[str]):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE scheduled_tasks SET last_run=CURRENT_TIMESTAMP, last_error=? WHERE id=?",
        (err or "", int(task_id)),
    )
    conn.commit()
    conn.close()


async def _task_group_summary(target_type: str, target_id: str, params: dict):
    if target_type != "group":
        await _smart_send(target_type, target_id, "⚠️ group_summary 只能推送到群")
        return
    from src.utils.database import db
    from src.plugins.ai_summary import generate_summary
    from src.utils.text_formatter import markdown_to_plain_text

    hours = int(params.get("hours", 6))
    min_messages = int(params.get("min_messages", 10))

    gid = int(target_id)
    messages = db.get_group_messages(gid, hours=hours, limit=500)
    if not messages or len(messages) < min_messages:
        return

    summary = await generate_summary(messages)
    summary = markdown_to_plain_text(summary)
    msg = f"📝 定时群聊总结（最近{hours}小时）：\n{summary}"
    await _smart_send("group", str(gid), msg)


async def _task_rss_digest(target_type: str, target_id: str, params: dict):
    # Reuse rss_sub logic (simplified)
    import feedparser
    from src.plugins.rss_sub import load_subs
    from src.utils.openai_client import openai_client
    from src.utils.text_formatter import markdown_to_plain_text

    subs = load_subs()
    subscriber_signature = {"type": target_type, "id": int(target_id)}

    recent_entries = []
    for url, data in subs.items():
        if subscriber_signature in data.get("subscribers", []):
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    recent_entries.append(f"- [{data['title']}] {entry.title}: {entry.link}")
            except Exception:
                pass

    if not recent_entries:
        await _smart_send(target_type, target_id, "暂无订阅或无近期更新。")
        return

    content_text = "\n".join(recent_entries[:20])
    prompt = (
        "你是一个研究助手。以下是用户 RSS 订阅的近期文章列表。"
        "请挑选出最重要的 5 篇文章。"
        "对于每一篇，提供标题、一句话的中文重要性总结，以及链接。"
        "请使用带编号的列表格式输出。\n\n"
        f"{content_text}"
    )
    digest = await openai_client.generate_content("auto", prompt, task_type="summary")
    digest = markdown_to_plain_text(digest)
    await _smart_send(target_type, target_id, f"📰 定时 RSS 摘要：\n{digest}")


async def _task_db_cleanup(target_type: str, target_id: str, params: dict):
    # cleanup old records; report stats
    from src.utils.database import db

    before = db.get_stats()
    conn = db._get_connection()  # type: ignore
    cur = conn.cursor()

    # conversations older than 7 days
    cur.execute("DELETE FROM conversations WHERE timestamp < datetime('now','-7 days')")
    # group_messages older than 14 days
    cur.execute("DELETE FROM group_messages WHERE timestamp < datetime('now','-14 days')")
    # group_context older than 6 hours
    cur.execute("DELETE FROM group_context WHERE timestamp < datetime('now','-6 hours')")
    # group_summaries older than 2 days
    cur.execute("DELETE FROM group_summaries WHERE timestamp < datetime('now','-2 days')")

    conn.commit()

    after = db.get_stats()
    msg = (
        "🧹 数据库清理完成\n"
        f"- total_conversations: {before.get('total_conversations')} -> {after.get('total_conversations')}\n"
        f"- total_group_messages: {before.get('total_group_messages')} -> {after.get('total_group_messages')}\n"
        f"- total_summaries: {before.get('total_summaries')} -> {after.get('total_summaries')}\n"
    )
    await _smart_send(target_type, target_id, msg)


def _load_tasks() -> list[dict]:
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM scheduled_tasks WHERE enabled=1")
    rows = cur.fetchall() or []
    conn.close()
    return [dict(r) for r in rows]


def _schedule_all():
    scheduler.remove_all_jobs()
    for t in _load_tasks():
        try:
            trig = _schedule_to_trigger(t["schedule_type"], t["schedule_value"])
            scheduler.add_job(_run_task, trig, args=[t], id=f"task_{t['id']}", replace_existing=True)
        except Exception as e:
            logger.error(f"[task] schedule failed id={t.get('id')}: {e}")


@driver.on_startup
async def _startup():
    _ensure_table()
    if not scheduler.running:
        scheduler.start()
    _schedule_all()


# Admin command group (allow both private & group)
task_cmd = on_command("task", aliases={"任务"}, priority=5)


@task_cmd.handle()
async def handle_task(event: GroupMessageEvent | PrivateMessageEvent):
    if not _is_admin(event):
        await task_cmd.finish("⚠️ 无权限（仅管理员可用）")

    raw = str(getattr(event, "message", "")).strip()
    parts = raw.split()
    if len(parts) < 2:
        await task_cmd.finish(
            "用法：\n"
            "  /task add <rss_digest|group_summary|db_cleanup> <daily HH:MM|hourly N|cron EXP> [target]\n"
            "  /task list\n"
            "  /task del <id>\n"
            "  /task run <id>\n"
            "target 支持: group:<群号> / private:<QQ号> / 纯数字（群里=群号，私聊=QQ号）\n"
        )

    sub = parts[1]

    if sub == "list":
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT id, task_type, schedule_type, schedule_value, target_type, target_id, enabled, last_run, last_error FROM scheduled_tasks ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall() or []
        conn.close()
        if not rows:
            await task_cmd.finish("暂无任务")
        lines = []
        for r in rows:
            lines.append(
                f"#{r['id']} {r['task_type']} | {r['schedule_type']} {r['schedule_value']} | {r['target_type']}:{r['target_id']} | last_run={r['last_run'] or '-'} | err={r['last_error'] or '-'}"
            )
        await task_cmd.finish("\n".join(lines))

    if sub == "del" and len(parts) >= 3:
        tid = int(parts[2])
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM scheduled_tasks WHERE id=?", (tid,))
        conn.commit()
        conn.close()
        _schedule_all()
        await task_cmd.finish(f"✅ 已删除任务 #{tid}")

    if sub == "run" and len(parts) >= 3:
        tid = int(parts[2])
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM scheduled_tasks WHERE id=?", (tid,))
        row = cur.fetchone()
        conn.close()
        if not row:
            await task_cmd.finish("⚠️ 任务不存在")
        await task_cmd.send(f"⏳ 正在执行任务 #{tid}...")
        await _run_task(dict(row))
        await task_cmd.finish("✅ 执行完成（如有输出将推送到目标）")

    if sub == "add":
        if len(parts) < 5:
            await task_cmd.finish("⚠️ 参数不足：/task add <type> <daily|hourly|cron> <value/expr> [target]")
        task_type = parts[2]
        schedule_type = parts[3]
        schedule_value = parts[4]
        target_raw = parts[5] if len(parts) >= 6 else ""
        target_type, target_id = _parse_target(target_raw, event)

        # validate trigger
        _schedule_to_trigger(schedule_type, schedule_value)

        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO scheduled_tasks (task_type, schedule_type, schedule_value, target_type, target_id, params, enabled) VALUES (?,?,?,?,?,?,1)",
            (task_type, schedule_type, schedule_value, target_type, target_id, "{}"),
        )
        conn.commit()
        tid = cur.lastrowid
        conn.close()

        _schedule_all()
        await task_cmd.finish(f"✅ 已创建任务 #{tid}: {task_type} @ {schedule_type} {schedule_value} -> {target_type}:{target_id}")

    await task_cmd.finish("⚠️ 未知子命令")
