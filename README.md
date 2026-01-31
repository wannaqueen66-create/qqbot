# qqbot (OpenClaw Bridge)

A **minimal QQ bot adapter**: NoneBot only handles QQ I/O (OneBot V11). All logic (chat/memory/tools/scheduling) is handled by **OpenClaw**.

## ✅ What this repo does
- Receive QQ messages via OneBot V11 (NapCat / Mirai)
- Forward messages to OpenClaw Gateway
- Return OpenClaw replies back to QQ

## ✅ Requirements
- Python 3.8+
- OneBot V11 provider (NapCat or Mirai)
- OpenClaw Gateway running

## ✅ Quick Start

### 1) Clone
```bash
git clone git@github.com:wannaqueen66-create/qqbot.git
cd qqbot
```

### 2) Create `.env`
```ini
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_TOKEN=your_gateway_token
OPENCLAW_SESSION_PREFIX=qq
OPENCLAW_TIMEOUT_SEC=60
```

> If `OPENCLAW_TOKEN` is empty, the bot will try to read:
> `/home/wannaqueen66/.openclaw/openclaw.json`

### 3) Install dependencies
```bash
python -m pip install -r requirements.txt
```

### 4) Run
```bash
python bot.py
```

## ✅ One-click Deploy
```bash
bash deploy.sh
```
Log file: `run.log`

## ✅ OpenClaw Cron (recommended)
All scheduling should be configured in OpenClaw. See:
- `DEPLOY_OPENCLAW.md`

## ✅ Notes
- This repo intentionally removes legacy plugin logic.
- Only `src/plugins/openclaw_bridge` is active.
