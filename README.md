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
- OneBot V11 provider (NapCat)
- OpenClaw Gateway running

## ✅ Fresh VPS Quick Start (Debian)
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin curl netcat-openbsd
sudo systemctl enable --now docker
```

## Setup

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

### 3) Health Check
```bash
bash healthcheck.sh
```

### 4) Run (Docker)
```bash
docker compose up -d --build
```

Logs:
```bash
docker compose logs -f qqbot
```

## NapCat Setup
See `NAPCAT_SETUP.md`.

## OpenClaw Cron
See `DEPLOY_OPENCLAW.md`.
