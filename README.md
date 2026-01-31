# qqbot

**Minimal QQ adapter for OpenClaw.**

This repo keeps only the required runtime surface:
- OneBot V11 input/output
- OpenClaw Gateway forwarding

All business logic (chat/memory/tools/schedules) lives in OpenClaw.

---

## Architecture
```
QQ (NapCat OneBot) → NoneBot → OpenClaw Gateway → Response → QQ
```

## Requirements
- Debian/Ubuntu VPS
- Docker + Docker Compose
- OpenClaw Gateway running

## ✅ Fresh VPS Quick Start (Debian)
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin curl netcat-openbsd npm
sudo systemctl enable --now docker
```

## ✅ Install OpenClaw (Required)
```bash
npm install -g openclaw
openclaw gateway start
openclaw status
```

## ✅ Install & Run (NapCat + qqbot)
This repo ships a **combined docker-compose.yml** with NapCat + qqbot.

### 1) Clone
```bash
git clone git@github.com:wannaqueen66-create/qqbot.git
cd qqbot
```

### 2) Environment
Create `.env`:
```ini
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_TOKEN=your_gateway_token
OPENCLAW_SESSION_PREFIX=qq
OPENCLAW_TIMEOUT_SEC=60
```

> If `OPENCLAW_TOKEN` is empty, the bot tries: `/home/wannaqueen66/.openclaw/openclaw.json`

### 3) Start
```bash
docker compose up -d --build
```

### 4) Login NapCat
Open WebUI:
```
http://<server-ip>:6099/webui
```
Login and configure Reverse WS:
```
ws://qqbot:8080/onebot/v11/ws
```

### 5) Health Check
```bash
bash healthcheck.sh
```

---

## ✅ Deployment Checklist (Must Pass)

### OpenClaw
- `openclaw status` shows Gateway running
- Gateway URL reachable at `ws://127.0.0.1:18789`

### NapCat
- WebUI 登录成功
- Reverse WS 已配置：`ws://qqbot:8080/onebot/v11/ws`
- 机器人能收到/发送 QQ 消息

### QQ Bot (this repo)
- `.env` 已填写
- `bash healthcheck.sh` 全部通过
- `docker compose ps` 显示 napcat/qqbot running

