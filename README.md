# QQBot (NapCat + NoneBot2) — OpenAI-Compatible Backend

一个基于 **NoneBot2 + OneBot V11 (NapCat)** 的 QQ 助手机器人。

- **LLM 后端**：通过 **Antigravity-Manager 提供的 OpenAI-compatible /v1 API** 接入（不直连 OpenAI/Claude/Gemini 官方）。
- **模型自动路由**：按任务/长度选择 `gemini-3-flash / gemini-3-pro-high / claude-sonnet-4.5-thinking / gemini-3-pro-image`。
- **部署方式**：默认 `network_mode: host`（确保容器可访问宿主机 `127.0.0.1:8045`）。

---

## Table of Contents / 目录

- [English](#english)
  - [Features](#features)
  - [Architecture](#architecture)
  - [Quick Start (VPS Docker)](#quick-start-vps-docker)
  - [NapCat Login & Reverse WS](#napcat-login--reverse-ws)
  - [Configuration (.env)](#configuration-env)
  - [Intelligent Model Routing](#intelligent-model-routing)
  - [Admin-only commands](#admin-only-commands)
  - [Chat Stats (水群榜)](#chat-stats-水群榜)
  - [Forwarded messages (合并转发)](#forwarded-messages-合并转发)
  - [Retries & Error handling](#retries--error-handling)
  - [Troubleshooting](#troubleshooting)
  - [Operations](#operations)
- [中文](#中文)
  - [功能](#功能)
  - [架构](#架构)
  - [快速开始（VPS Docker）](#快速开始vps-docker)
  - [NapCat 登录与反向 WS](#napcat-登录与反向-ws)
  - [配置（.env）](#配置env)
  - [智能模型路由](#智能模型路由)
  - [管理员命令](#管理员命令)
  - [水群榜](#水群榜)
  - [合并转发](#合并转发)
  - [重试与错误处理](#重试与错误处理)
  - [故障排查](#故障排查)
  - [运维](#运维)

---

## English

### Features

- Basic: `/ping` (在吗), `/help` (帮助/菜单)
- Chat:
  - Group: `@bot <message>` (group requires @)
  - Private: direct message
  - Three-tier memory (SQLite)
  - `/clear` reset personal memory, `/memory` stats
- RSS: `/add_rss`, `/rss list`, `/rss del`, `/rss_digest`
- Reminders: `/remind add`, `/remind list`, `/remind del`
- Weather: `/weather` / `/天气`
- Summary:
  - Manual: `/summary` (group only)
  - Scheduled: 12:00 / 18:00 / 00:00 / 06:00 (Asia/Shanghai)
- Status: `/status` (admin-only, private chat only)

### Architecture

```
QQ (NapCat OneBot)  ->  NoneBot2 (this repo)  ->  Antigravity-Manager (/v1)  ->  QQ
         ^                        |
         |---- Reverse WebSocket -|
```

### Quick Start (VPS Docker)

1) Install Docker (Debian/Ubuntu):

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

2) Clone:

```bash
cd /opt
git clone https://github.com/wannaqueen66-create/qqbot.git
cd qqbot
```

3) Create `.env`:

```bash
cp .env.example .env
nano .env
```

4) Start:

```bash
docker-compose up -d --build
```

> `docker-compose.yml` uses `network_mode: host` so the bot can call local Antigravity on `127.0.0.1:8045`.

### NapCat Login & Reverse WS

- WebUI: `http://<VPS_PUBLIC_IP>:6099/webui`
- Login: scan QR code
- Reverse WebSocket (NapCat WebUI -> Network):
  - `ws://127.0.0.1:8080/onebot/v11/ws`

### Configuration (.env)

Required:

```ini
# OpenAI-compatible backend
OPENAI_BASE_URL=http://127.0.0.1:8045/v1
OPENAI_API_KEY=YOUR_KEY
OPENAI_MODEL=auto
```

Optional (recommended defaults):

```ini
# Intelligent routing
MODEL_CHAT_SHORT=gemini-3-flash
MODEL_CHAT_LONG=gemini-3-pro-high
MODEL_SUMMARY=claude-sonnet-4.5-thinking
MODEL_IMAGE=gemini-3-pro-image

# Admin-only commands
ADMIN_USER_IDS=[YOUR_QQ_ID]

# Retry
OPENAI_MAX_RETRIES=2
OPENAI_RETRY_BASE_SEC=0.6

# Forwarding
FORWARD_THRESHOLD=100
BOT_NICKNAME=AI 助手

# Scheduled push targets
TARGET_GROUPS=[]
```

### Intelligent Model Routing

When `OPENAI_MODEL=auto`:

- Short chat (<150 chars) -> `MODEL_CHAT_SHORT`
- Long chat (>=150 chars) -> `MODEL_CHAT_LONG`
- Summary tasks -> `MODEL_SUMMARY`
- Image tasks -> `MODEL_IMAGE`

> Actual model ids should match Antigravity-Manager “Supported Models” list.

### Admin-only commands

- `/status` is **admin-only** and **private-chat only**.
- Configure admins via `ADMIN_USER_IDS` (JSON list or comma-separated). Default: [ADMIN_QQ_ID].

### Chat Stats (水群榜)

Commands (group):

- `/水群榜` (aliases: `/聊天榜`, `/发言榜`)

Config (optional):

```ini
ENABLE_CHAT_STATS=true
STATS_PUSH_HOUR=23
STATS_TOP_COUNT=10
STATS_FILE=data/chat_stats.json
```

### Forwarded messages (合并转发)

Long replies will be sent as **forwarded messages** to reduce spam.

Config:

```ini
FORWARD_THRESHOLD=100
BOT_NICKNAME=AI 助手
```

If forward message fails (anti-spam), it will fall back to normal send.

### Retries & Error handling

OpenAI requests retry on network errors / 429 / 5xx.

Config:

```ini
OPENAI_MAX_RETRIES=2
OPENAI_RETRY_BASE_SEC=0.6
```

### Security & Privacy

- **Do NOT commit** `.env`, `napcat/`, or `data/` to public repos.
- Do not put real QQ IDs or private domains in docs; use placeholders.

### Troubleshooting

1) WS keeps reconnecting / no reply
- Ensure NapCat reverse WS is `ws://127.0.0.1:8080/onebot/v11/ws` (NOT `ws://qqbot:8080/...` in host network)
- Check logs:
  - `docker-compose logs -f napcat`
  - `docker-compose logs -f bot`

2) `/status` returns "无权限"
- Must be private chat
- `user_id` must be in `ADMIN_USER_IDS`

3) LLM call fails
- Check `OPENAI_BASE_URL` and `OPENAI_API_KEY`
- Try `/status` (admin) to verify env is loaded

### Operations

- Logs: `docker-compose logs -f`
- Restart: `docker-compose restart`
- Stop: `docker-compose down`

---

## 中文

### 功能

- 基础：`/ping`（在吗）、`/help`（帮助/菜单）
- 聊天：
  - 群聊：必须 `@机器人` 才回复
  - 私聊：直接发消息即可
  - 三层记忆（SQLite 持久化）
  - `/clear` 清空记忆、`/memory` 查看统计
- RSS：`/add_rss`、`/rss list`、`/rss del`、`/rss_digest`
- 提醒：`/remind add`、`/remind list`、`/remind del`
- 天气：`/weather` / `/天气`
- 总结：
  - 手动：`/summary`（仅群聊）
  - 定时：12:00 / 18:00 / 00:00 / 06:00（上海时区）
- 状态：`/status`（仅管理员私聊可用）

### 架构

```
QQ (NapCat OneBot)  ->  NoneBot2 (本项目)  ->  Antigravity-Manager (/v1)  ->  QQ
         ^                        |
         |---- Reverse WebSocket -|
```

### 快速开始（VPS Docker）

1) 安装 Docker（Debian/Ubuntu）：

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

2) 克隆：

```bash
cd /opt
git clone https://github.com/wannaqueen66-create/qqbot.git
cd qqbot
```

3) 配置 `.env`：

```bash
cp .env.example .env
nano .env
```

4) 启动：

```bash
docker-compose up -d --build
```

> 默认 compose 使用 `network_mode: host`，确保容器能访问宿主机 `127.0.0.1:8045` 的 Antigravity。

### NapCat 登录与反向 WS

- WebUI：`http://<VPS公网IP>:6099/webui`
- 扫码登录 QQ
- 反向 WS（WebUI -> Network）：`ws://127.0.0.1:8080/onebot/v11/ws`

### 配置（.env）

必需：

```ini
OPENAI_BASE_URL=http://127.0.0.1:8045/v1
OPENAI_API_KEY=你的KEY
OPENAI_MODEL=auto
```

可选（推荐）：

```ini
MODEL_CHAT_SHORT=gemini-3-flash
MODEL_CHAT_LONG=gemini-3-pro-high
MODEL_SUMMARY=claude-sonnet-4.5-thinking
MODEL_IMAGE=gemini-3-pro-image

ADMIN_USER_IDS=[YOUR_QQ_ID]

OPENAI_MAX_RETRIES=2
OPENAI_RETRY_BASE_SEC=0.6

FORWARD_THRESHOLD=100
BOT_NICKNAME=AI 助手

TARGET_GROUPS=[]
```

### 智能模型路由

当 `OPENAI_MODEL=auto` 时：

- 短对话（<150 字符）-> `MODEL_CHAT_SHORT`
- 长对话（>=150 字符）-> `MODEL_CHAT_LONG`
- 总结类任务 -> `MODEL_SUMMARY`
- 图片类任务 -> `MODEL_IMAGE`

### 管理员命令

- `/status` 仅管理员私聊可用。
- 管理员通过 `ADMIN_USER_IDS` 配置（JSON 列表或逗号分隔），默认 [ADMIN_QQ_ID]。

### 水群榜

群聊命令：

- `/水群榜`（别名：`/聊天榜`、`/发言榜`）

配置（可选）：

```ini
ENABLE_CHAT_STATS=true
STATS_PUSH_HOUR=23
STATS_TOP_COUNT=10
STATS_FILE=data/chat_stats.json
```

### 合并转发

AI 长回复超过阈值会自动用“合并转发”发送，减少刷屏。

```ini
FORWARD_THRESHOLD=100
BOT_NICKNAME=AI 助手
```

### 重试与错误处理

对网络错误 / 429 / 5xx 会自动重试。

```ini
OPENAI_MAX_RETRIES=2
OPENAI_RETRY_BASE_SEC=0.6
```

### 安全与隐私

- **不要提交** `.env`、`napcat/`、`data/` 到公开仓库。
- 文档里不要写真实 QQ 号/私人域名，统一使用占位符。

### 故障排查

1) WS 频繁重连 / 不回复
- host 网络模式下，NapCat 反向 WS 必须是：`ws://127.0.0.1:8080/onebot/v11/ws`
- 查看日志：
  - `docker-compose logs -f napcat`
  - `docker-compose logs -f bot`

2) `/status` 提示无权限
- 必须私聊
- QQ 号必须在 `ADMIN_USER_IDS`

3) 模型调用失败
- 检查 `OPENAI_BASE_URL`、`OPENAI_API_KEY`
- 管理员私聊 `/status` 看配置是否加载

### 运维

- 看日志：`docker-compose logs -f`
- 重启：`docker-compose restart`
- 停止：`docker-compose down`
