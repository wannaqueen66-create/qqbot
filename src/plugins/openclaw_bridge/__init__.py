import asyncio
import json
import os
import uuid
from typing import Optional

import aiohttp
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, Event

OPENCLAW_GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "ws://127.0.0.1:18789")
OPENCLAW_TOKEN = os.getenv("OPENCLAW_TOKEN")
OPENCLAW_SESSION_PREFIX = os.getenv("OPENCLAW_SESSION_PREFIX", "qq")
OPENCLAW_TIMEOUT_SEC = int(os.getenv("OPENCLAW_TIMEOUT_SEC", "60"))


def _load_token_from_openclaw_config() -> Optional[str]:
    try:
        path = os.getenv("OPENCLAW_CONFIG_PATH", "/home/wannaqueen66/.openclaw/openclaw.json")
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("gateway", {}).get("auth", {}).get("token")
    except Exception:
        return None


def _extract_text(message_payload: dict) -> str:
    content = message_payload.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join([p for p in parts if p])
    return str(message_payload) if message_payload else ""


async def openclaw_chat(message: str, session_key: str) -> str:
    token = OPENCLAW_TOKEN or _load_token_from_openclaw_config()
    if not token:
        return "未配置 OPENCLAW_TOKEN，无法转发。"

    client_id = str(uuid.uuid4())
    chat_run_id = str(uuid.uuid4())
    timeout = OPENCLAW_TIMEOUT_SEC

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(OPENCLAW_GATEWAY_URL, heartbeat=15) as ws:
            # Read any pre-connect events (like challenge) but don't block long
            try:
                await ws.receive(timeout=1)
            except Exception:
                pass

            connect_req = {
                "type": "req",
                "id": client_id,
                "method": "connect",
                "params": {
                    "minProtocol": 1,
                    "maxProtocol": 1,
                    "client": {
                        "id": "qq-bridge",
                        "version": "0.1.0",
                        "platform": "linux",
                        "mode": "operator",
                    },
                    "role": "operator",
                    "scopes": ["operator.read", "operator.write"],
                    "auth": {"token": token},
                },
            }
            await ws.send_json(connect_req)

            # Wait for connect ack
            while True:
                msg = await ws.receive(timeout=5)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "res" and data.get("id") == client_id:
                        if not data.get("ok"):
                            return f"OpenClaw 连接失败: {data.get('error') or data.get('payload')}"
                        break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    return "OpenClaw 连接失败"

            chat_req = {
                "type": "req",
                "id": str(uuid.uuid4()),
                "method": "chat.send",
                "params": {
                    "sessionKey": session_key,
                    "message": message,
                    "idempotencyKey": chat_run_id,
                    "deliver": False,
                },
            }
            await ws.send_json(chat_req)

            # Wait for chat final
            end_time = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = end_time - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return "OpenClaw 响应超时。"
                msg = await ws.receive(timeout=min(5, remaining))
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "event" and data.get("event") == "chat":
                        payload = data.get("payload", {})
                        if payload.get("runId") != chat_run_id:
                            continue
                        if payload.get("state") == "final" and payload.get("message", {}).get("role") == "assistant":
                            return _extract_text(payload.get("message", {})) or ""
                        if payload.get("state") in ("error", "aborted"):
                            return payload.get("errorMessage") or "OpenClaw 返回错误"
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    return "OpenClaw 连接中断"


matcher = on_message(priority=1, block=True)


@matcher.handle()
async def _(bot: Bot, event: Event):
    text = event.get_plaintext().strip()
    if not text:
        return

    if event.message_type == "group":
        session_key = f"{OPENCLAW_SESSION_PREFIX}:group:{event.group_id}"
    else:
        session_key = f"{OPENCLAW_SESSION_PREFIX}:user:{event.user_id}"

    reply = await openclaw_chat(text, session_key)
    if reply:
        await bot.send(event, reply)
