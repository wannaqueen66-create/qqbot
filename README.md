# QQ Robot

A personal assistant bot based on [NoneBot2](https://v2.nonebot.dev/), fully containerized for easy deployment.

## Features

- **Basic Interaction**: `/ping` (在吗), `/help` (帮助/菜单)
- **Chat**: `@bot <message>` (Group) / direct message (Private)
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
- Example base URL: `https://anti.freeapp.tech/v1`

Environment variables:
- `OPENAI_BASE_URL` (e.g. `https://anti.freeapp.tech/v1`)
- `OPENAI_API_KEY` (your API key)
- `OPENAI_MODEL` (default: `gpt-4o-mini`)

## 🚀 Quick Start (Docker)

The entire project (Bot + NapCat) is containerized.

### 1) Start services

```bash
docker-compose up -d
```

This will start:
- **NapCat**: OneBot provider (QQ protocol)
- **QQBot**: Python bot logic (NoneBot2)

### 2) Configure NapCat (first time)

1. Open **http://localhost:6099/webui**
2. Login by scanning QR code with QQ mobile
3. Verify Reverse WebSocket:
   - URL: `ws://qqbot:8080/onebot/v11/ws`
   - Enable: `true`

### 3) Configure env

```bash
cp .env.example .env
```

Edit `.env`:

```ini
HOST=0.0.0.0
PORT=8080
TZ=Asia/Shanghai

OPENAI_BASE_URL=https://anti.freeapp.tech/v1
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-4o-mini

OPENWEATHER_API_KEY=your_openweather_api_key
TARGET_GROUPS=["12345678"]
FORWARD_THRESHOLD=100
```

### 4) Verify

```bash
docker-compose logs -f bot
```

## Notes

- Group chat replies require **@bot**.
- Private chat replies should work directly.
- Current OpenAI-compatible mode is **text-only** (images/audio/video are not processed yet).

## Management

- Stop: `docker-compose down`
- Restart: `docker-compose restart`
- Update: `docker-compose pull && docker-compose up -d --build`
