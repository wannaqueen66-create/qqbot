# qqbot

**Minimal QQ adapter for OpenClaw.**  
**OpenClaw 的最小化 QQ 适配器。**

This repo keeps only the required runtime surface:  
本项目仅保留必要的运行层：
- OneBot V11 input/output  
- OpenClaw Gateway forwarding

All business logic (chat/memory/tools/schedules) lives in OpenClaw.  
所有业务逻辑（对话/记忆/工具/调度）均由 OpenClaw 负责。

---

## Architecture | 架构
```
QQ (NapCat OneBot) → NoneBot → OpenClaw Gateway → Response → QQ
```

## Requirements | 环境要求
- Debian/Ubuntu VPS
- Docker + Docker Compose
- OpenClaw Gateway running

## ✅ Fresh VPS Quick Start (Debian) | 全新 VPS 快速开始
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin curl netcat-openbsd npm
sudo systemctl enable --now docker
```

## ✅ Install OpenClaw (Required) | 安装 OpenClaw（必需）
```bash
npm install -g openclaw
openclaw gateway start
openclaw status
```

## ✅ Install & Run (NapCat + qqbot) | 安装并运行（NapCat + qqbot）
This repo ships a **combined docker-compose.yml** with NapCat + qqbot.  
本仓库内置 NapCat + qqbot 的统一 `docker-compose.yml`。

### 1) Clone | 克隆
```bash
git clone git@github.com:wannaqueen66-create/qqbot.git
cd qqbot
```

### 2) Environment | 环境变量
Create `.env`:  
创建 `.env`：
```ini
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_TOKEN=your_gateway_token
OPENCLAW_SESSION_PREFIX=qq
OPENCLAW_TIMEOUT_SEC=60
```

> If `OPENCLAW_TOKEN` is empty, the bot tries: `/home/wannaqueen66/.openclaw/openclaw.json`  
> 若未设置 `OPENCLAW_TOKEN`，会尝试读取：`/home/wannaqueen66/.openclaw/openclaw.json`

### 3) Start | 启动
```bash
docker compose up -d --build
```

### 4) Login NapCat | 登录 NapCat
Open WebUI:  
打开 WebUI：
```
http://<server-ip>:6099/webui
```
Login and configure Reverse WS:  
登录并配置反向 WS：
```
ws://qqbot:8080/onebot/v11/ws
```

### 5) Health Check | 健康检查
```bash
bash healthcheck.sh
```

---

## ✅ Deployment Checklist (Must Pass) | 部署检查清单（必须通过）

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

