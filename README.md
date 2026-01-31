# qqbot (OpenClaw Bridge)

Phase 1 architecture: **NoneBot only handles QQ I/O**, all messages are forwarded to **OpenClaw** for reasoning and response generation.

## What it does (Phase 1)
- Receive QQ messages via OneBot V11 (NapCat)
- Forward to OpenClaw Gateway
- Return OpenClaw responses back to QQ

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
- This branch only includes the OpenClaw bridge plugin.
- Original features in `main` are intentionally bypassed in Phase 1.
