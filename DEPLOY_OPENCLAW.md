# 部署说明（OpenClaw 方案）

本项目在 Phase 3 下仅做 QQ I/O 转发，所有逻辑由 OpenClaw 负责。

## 1. 前置条件
- 已安装并运行 OpenClaw Gateway
- 已有 OneBot V11（NapCat/Mirai）提供 QQ 通道

## 2. 环境变量
```ini
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_TOKEN=你的gateway token
OPENCLAW_SESSION_PREFIX=qq
OPENCLAW_TIMEOUT_SEC=60
```

若未设置 `OPENCLAW_TOKEN`，会尝试读取：
`/home/wannaqueen66/.openclaw/openclaw.json`

## 3. 启动
```bash
python bot.py
```

## 4. OpenClaw 侧定时任务（示例）
以下 cron 建议在 OpenClaw 内配置，用于替代旧插件的定时功能：

### 4.1 每日全球新闻（20:00 上海）
```
openclaw cron add --name "Daily Global News" --cron "0 20 * * *" --tz "Asia/Shanghai" \
  --session isolated \
  --message "Provide a concise daily news brief: Global top 10 headlines today with emphasis on technology and cryptocurrency. Output in Chinese only. For each item: numbered list (1-10), then a single Chinese paragraph (<=100 Chinese characters) describing the news, followed by the original URL on the same line. No title, no extra sections." \
  --deliver --channel telegram --to 7791250692
```

### 4.2 每日加密快照（09:00 上海）
```
openclaw cron add --name "Daily Crypto Snapshot" --cron "0 9 * * *" --tz "Asia/Shanghai" \
  --session isolated \
  --message "Provide a daily crypto market snapshot for BTC/ETH/SOL with top 10 relevant items. Output in Chinese only. For each item: numbered list (1-10), then a single Chinese paragraph (<=100 Chinese characters) describing the item (price moves, drivers, notable events), followed by the original URL on the same line. No title, no extra sections." \
  --deliver --channel telegram --to 7791250692
```

### 4.3 每日待办清单（08:00 上海）
```
openclaw cron add --name "Morning Status Checklist" --cron "0 8 * * *" --tz "Asia/Shanghai" \
  --session isolated \
  --message "Prepare a concise status checklist for Lucas. Include: (1) Active projects and status, (2) Paused items and blockers, (3) Next best actions. Output in Chinese, bullet list, no markdown tables." \
  --deliver --channel telegram --to 7791250692
```

> 如需改推送对象或时间，请调整 `--to` 与 `--cron/--tz`。
