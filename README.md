# qqbot (OpenClaw Bridge)

Phase 1–2 architecture: **NoneBot only handles QQ I/O**, all messages are forwarded to **OpenClaw** for reasoning and response generation. Legacy features are intentionally bypassed in Phase 2.

## What it does (Phase 2)
- Receive QQ messages via OneBot V11 (NapCat)
- Forward to OpenClaw Gateway
- Return OpenClaw responses back to QQ
- `/help` / `/summary` are mapped to OpenClaw intents

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
- Phase 2 disables legacy plugin behaviors (chat/memory/stats/rss/etc.).
- Phase 3 will migrate schedulers and RSS into OpenClaw.
