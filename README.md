# QQ Robot

A personal assistant bot based on [NoneBot2](https://v2.nonebot.dev/), fully containerized for easy deployment.

## Features

- **Basic Interaction**: `/ping` (在吗), `/help` (帮助/菜单)
- **Chat**:
  - **Group**: `@bot <message>` (群聊必须 @ 才回复)
  - **Private**: direct message works
  - **Three-tier memory**:
    - Tier 1: Personal short-term memory
    - Tier 2: Shared group context (recent topics)
    - Tier 3: Long-term summaries (from `/summary` and scheduled summaries)
  - `/clear` (清空记忆): Reset personal memory
  - `/memory` (记忆统计): View memory usage stats
- **RSS Subscription**:
  - `/add_rss <url>` (订阅)
  - `/rss list` (订阅列表)
  - `/rss del <url>`
  - `/rss_digest`: AI-powered daily summary of Top 5 articles
- **Reminders**: `/remind add <time> <content>`, `/remind list`, `/remind del <id>`
- **Weather**: `/weather [city]` or `/天气 [城市]` (Default: Guangzhou). Powered by **OpenWeatherMap**.
- **AI Summary**:
  - Manual: `/summary` (总结) (Group only)
  - Scheduled: 12:00 / 18:00 / 00:00 / 06:00 (Asia/Shanghai)

## LLM Backend (OpenAI-Compatible)

This project uses an **OpenAI-compatible API** (OpenAI protocol) for chat and summarization.

Recommended setup:
- Use **Antigravity-Manager** as a secure reverse proxy for `/v1/*`.
- On the same VPS, you can call it locally: `http://127.0.0.1:8045/v1`

Environment variables:
- `OPENAI_BASE_URL` (e.g. `http://127.0.0.1:8045/v1` or `https://anti.freeapp.tech/v1`)
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (set to `auto` to enable routing)

### Intelligent model routing

When `OPENAI_MODEL=auto`, the bot will choose model by task:

- Short chat (<150 chars) -> `MODEL_CHAT_SHORT` (default: `gemini-3-flash`)
- Long chat (>=150 chars) -> `MODEL_CHAT_LONG` (default: `gemini-3-pro-high`)
- Summary tasks -> `MODEL_SUMMARY` (default: `claude-sonnet-4.5-thinking`)
- Image tasks -> `MODEL_IMAGE` (default: `gemini-3-pro-image`)

> Actual model ids come from Antigravity-Manager “Supported Models” list.

## 🚀 Quick Start (Docker)

### 1) Configure env

```bash
cp .env.example .env
```

Fill `.env`:

```ini
OPENAI_BASE_URL=http://127.0.0.1:8045/v1
OPENAI_API_KEY=YOUR_KEY
OPENAI_MODEL=auto

MODEL_CHAT_SHORT=gemini-3-flash
MODEL_CHAT_LONG=gemini-3-pro-high
MODEL_SUMMARY=claude-sonnet-4.5-thinking
MODEL_IMAGE=gemini-3-pro-image
```

### 2) Start services

```bash
docker-compose up -d --build
```

This will start:
- **NapCat**: OneBot provider (QQ protocol)
- **QQBot**: Python bot logic (NoneBot2)

> Default `docker-compose.yml` uses `network_mode: host` so the bot can access local Antigravity `127.0.0.1:8045`.

### 3) Configure NapCat (first time)

1. Open WebUI: `http://<VPS公网IP>:6099/webui`
2. Login by scanning QR code with QQ mobile
3. Verify Reverse WebSocket:
   - URL: `ws://127.0.0.1:8080/onebot/v11/ws`
   - Enable: `true`

## Notes

- `/status` is **admin-only** and **private-chat only**. Configure via `ADMIN_USER_IDS`.

- Current OpenAI-compatible mode is **text-only** (images/audio/video are not processed yet).

## Management

- Stop: `docker-compose down`
- Restart: `docker-compose restart`
- Logs: `docker-compose logs -f`
