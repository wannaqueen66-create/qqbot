# QQ Robot

A personal assistant bot based on [NoneBot2](https://v2.nonebot.dev/), now fully containerized for easy deployment.

## Features

- **Basic Interaction**: `/ping` (在吗), `/help` (帮助/菜单)
- **Chat**: `@bot <message>` (Group/Private) - **Three-tier intelligent memory system**:
  - **Tier 1**: Personal short-term memory (3 rounds per user, 10 min)
  - **Tier 2**: Shared group context (recent topics, 30 min)
  - **Tier 3**: Long-term summaries (preserved from daily summaries)
  - `/clear` (清空记忆): Reset personal memory
  - `/memory` (记忆统计): View memory usage stats
- **RSS Subscription**: 
    - `/add_rss <url>` (订阅): Subscribe (Group/Private isolated).
    - `/rss list` (订阅列表): List subscriptions.
    - `/rss del <url>`: Unsubscribe.
    - `/rss_digest`: AI-powered daily summary of Top 5 articles.
- **Reminders**: `/remind add <time> <content>` (提醒), `/remind list`, `/remind del <id>`.
- **Weather**: `/weather [city]` or `/天气 [城市]` (Default: Guangzhou). Powered by **OpenWeatherMap**.
- **AI Summary**: 
    - Manual: `/summary` (总结) (Group only).
    - Scheduled: Daily summaries at 12:00, 18:00, 00:00, 06:00.

## 🚀 Quick Start (Docker)

The entire project (Bot + NapCat) is containerized. You only need Docker and Docker Compose.

### 1. Start Services

```bash
docker-compose up -d
```

This will start:
- **NapCat**: The OneBot provider (handles QQ protocol).
- **QQBot**: The Python bot logic.

### 2. Configure NapCat (First Time)

1.  Open **[http://localhost:6099/webui](http://localhost:6099/webui)** in your browser.
    *   *Tip: If asked for a Token, run `docker compose logs napcat | grep Token`*
2.  **Login**: Scan the QR code with your QQ mobile app.
3.  **Verify Connection**: 
    - The setup attempts to auto-configure the connection.
    - If not connected, go to **Network Configuration** in the Web UI and ensure a **Reverse WebSocket** is added:
        - URL: `ws://qqbot:8080/onebot/v11/ws`
        - Enable: `true`

### 3. Verify Bot

Check the bot logs to confirm it's connected:

```bash
docker-compose logs -f bot
```

## Configuration

Configuration is managed via the `.env` file.

1.  **Copy the example file:**
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`** and fill in your API keys and Group IDs.

```ini
DRIVER=~fastapi
HOST=0.0.0.0  # Must be 0.0.0.0 for Docker
PORT=8080
LOG_LEVEL=INFO

# Gemini API Keys (Supports multiple keys for load balancing)
GEMINI_API_KEYS=["your_key_1", "your_key_2"]

# OpenWeatherMap (Required for Weather)
OPENWEATHER_API_KEY=your_openweather_api_key

# Target Groups for Scheduled Pushes (Daily Weather, Summaries)
# List of Group IDs (numbers only). 
# Note: Chat and Commands work in ALL groups by default.
TARGET_GROUPS=["12345678"]
```

### Intelligent Model Selection (Quality-First)

The bot automatically selects the optimal Gemini 2.5 model based on task:

- **Chat (Very Short < 30 chars)**: `flash-lite` (minimal responses)
- **Chat (Short 30-150 chars)**: `flash` (daily conversation)
- **Chat (Long > 150 chars)**: `pro` (complex questions, better understanding)
- **Summary (< 500 chars)**: `flash`
- **Summary (> 500 chars)**: `pro` (higher quality summaries)

## Directory Structure

- `src/`: Bot source code (mounted, hot-reload capable).
- `napcat/config/`: NapCat configuration.
- `napcat/qq/`: NapCat session data (Keep safe!).
- `docker-compose.yml`: Service definition.

## Management Commands

- **Stop**: `docker-compose down`
- **Restart**: `docker-compose restart`
- **Update**: `docker-compose pull && docker-compose up -d --build`
