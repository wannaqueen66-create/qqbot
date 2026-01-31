# qqbot (OpenClaw Bridge)

Phase 3 architecture: **NoneBot is a thin QQ adapter**. All logic (chat, memory, RSS, reminders, summaries, scheduling) is handled by **OpenClaw**.

## What it does (Phase 3)
- Receive QQ messages via OneBot V11 (NapCat)
- Forward to OpenClaw Gateway
- Return OpenClaw responses back to QQ
- Legacy plugins and utilities removed

## Configuration
Set these environment variables:

```ini
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_TOKEN=your_gateway_token
OPENCLAW_SESSION_PREFIX=qq
OPENCLAW_TIMEOUT_SEC=60
```

If `OPENCLAW_TOKEN` is not set, the bridge will attempt to read it from:
`/home/wannaqueen66/.openclaw/openclaw.json`

## Development
```bash
python bot.py
```

## Notes
- All scheduling is expected to be configured in OpenClaw (cron).
- This repo no longer ships legacy features.
