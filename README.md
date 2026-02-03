# QQBot (NapCat + NoneBot2) — OpenAI-Compatible Backend

一个基于 **NoneBot2 + OneBot V11(NapCat)** 的 QQ 助手机器人项目。模型能力通过 **Antigravity-Manager 提供的 OpenAI-compatible /v1 API** 接入，并支持按任务自动路由模型。

---

## Table of Contents / 目录

- [English](#english)
  - [Features](#features)
  - [LLM Backend (OpenAI-Compatible)](#llm-backend-openai-compatible)
  - [Intelligent Model Routing](#intelligent-model-routing)
  - [Quick Start (Docker on VPS)](#quick-start-docker-on-vps)
  - [NapCat Login & Reverse WS](#napcat-login--reverse-ws)
  - [Operations](#operations)
  - [Notes](#notes)
- [中文](#中文)
  - [功能](#功能)
  - [LLM 后端（OpenAI 兼容协议）](#llm-后端openai-兼容协议)
  - [智能模型路由](#智能模型路由)
  - [快速开始（VPS Docker 部署）](#快速开始vps-docker-部署)
  - [NapCat 登录与反向 WS](#napcat-登录与反向-ws)
  - [运维](#运维)
  - [注意事项](#注意事项)

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

### LLM Backend (OpenAI-Compatible)

This project talks to an **OpenAI-compatible** API (OpenAI protocol), recommended to be provided by **Antigravity-Manager**.

- Local on the same VPS: `http://127.0.0.1:8045/v1`
- Or via your domain: `https://anti.freeapp.tech/v1`

Required env:
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (set to `auto` to enable routing)

### Intelligent Model Routing

When `OPENAI_MODEL=auto`, the bot selects models by task:

- Short chat (<150 chars) -> `MODEL_CHAT_SHORT` (default: `gemini-3-flash`)
- Long chat (>=150 chars) -> `MODEL_CHAT_LONG` (default: `gemini-3-pro-high`)
- Summary tasks -> `MODEL_SUMMARY` (default: `claude-sonnet-4.5-thinking`)
- Image tasks -> `MODEL_IMAGE` (default: `gemini-3-pro-image`)

Retry knobs (optional):
- `OPENAI_MAX_RETRIES` (default 2)
- `OPENAI_RETRY_BASE_SEC` (default 0.6)

### Quick Start (Docker on VPS)

> Default `docker-compose.yml` uses `network_mode: host` so the bot can call local Antigravity on `127.0.0.1:8045`.

1) Configure env:

```bash
cp .env.example .env
```

Edit `.env` (example):

```ini
OPENAI_BASE_URL=http://127.0.0.1:8045/v1
OPENAI_API_KEY=YOUR_KEY
OPENAI_MODEL=auto

MODEL_CHAT_SHORT=gemini-3-flash
MODEL_CHAT_LONG=gemini-3-pro-high
MODEL_SUMMARY=claude-sonnet-4.5-thinking
MODEL_IMAGE=gemini-3-pro-image

# Admin-only commands
ADMIN_USER_IDS=[375024323]

OPENAI_MAX_RETRIES=2
OPENAI_RETRY_BASE_SEC=0.6
```

2) Start:

```bash
docker-compose up -d --build
```

### NapCat Login & Reverse WS

- WebUI: `http://<VPS_PUBLIC_IP>:6099/webui`
- Login: scan QR code
- Reverse WS (WebUI -> Network): `ws://127.0.0.1:8080/onebot/v11/ws`

### Operations

- Logs: `docker-compose logs -f`
- Restart: `docker-compose restart`
- Stop: `docker-compose down`

### Notes

- Group chat replies require **@bot**.
- `/status` is **admin-only** and **private-chat only**.
- Current OpenAI-compatible mode is text-first.

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

### LLM 后端（OpenAI 兼容协议）

本项目通过 **OpenAI 协议**调用模型，推荐使用 **Antigravity-Manager** 做统一反代与模型管理。

- VPS 本机：`http://127.0.0.1:8045/v1`
- 域名：`https://anti.freeapp.tech/v1`

必需环境变量：
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`（设为 `auto` 开启智能路由）

### 智能模型路由

当 `OPENAI_MODEL=auto` 时，根据任务自动选择模型：

- 短对话（<150 字符）-> `MODEL_CHAT_SHORT`（默认 `gemini-3-flash`）
- 长对话（>=150 字符）-> `MODEL_CHAT_LONG`（默认 `gemini-3-pro-high`）
- 总结类任务 -> `MODEL_SUMMARY`（默认 `claude-sonnet-4.5-thinking`）
- 图片类任务 -> `MODEL_IMAGE`（默认 `gemini-3-pro-image`）

可选重试参数：
- `OPENAI_MAX_RETRIES`（默认 2）
- `OPENAI_RETRY_BASE_SEC`（默认 0.6）

### 快速开始（VPS Docker 部署）

> 默认 compose 使用 `network_mode: host`，这样 qqbot 才能访问本机 `127.0.0.1:8045` 的 Antigravity。

1) 配置环境变量：

```bash
cp .env.example .env
```

编辑 `.env`（示例）：

```ini
OPENAI_BASE_URL=http://127.0.0.1:8045/v1
OPENAI_API_KEY=你的KEY
OPENAI_MODEL=auto

MODEL_CHAT_SHORT=gemini-3-flash
MODEL_CHAT_LONG=gemini-3-pro-high
MODEL_SUMMARY=claude-sonnet-4.5-thinking
MODEL_IMAGE=gemini-3-pro-image

ADMIN_USER_IDS=[375024323]

OPENAI_MAX_RETRIES=2
OPENAI_RETRY_BASE_SEC=0.6
```

2) 启动：

```bash
docker-compose up -d --build
```

### NapCat 登录与反向 WS

- WebUI：`http://<VPS公网IP>:6099/webui`
- 扫码登录 QQ
- 反向 WS（WebUI -> Network）：`ws://127.0.0.1:8080/onebot/v11/ws`

### 运维

- 看日志：`docker-compose logs -f`
- 重启：`docker-compose restart`
- 停止：`docker-compose down`

### 注意事项

- 群里必须 @ 才回复。
- `/status` 仅管理员私聊可用（由 `ADMIN_USER_IDS` 控制）。
- 当前版本以“文本优先”，多模态后续可扩展。
