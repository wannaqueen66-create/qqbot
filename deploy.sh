#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -f ".env" ]; then
  cat > .env <<'ENV'
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_TOKEN=
OPENCLAW_SESSION_PREFIX=qq
OPENCLAW_TIMEOUT_SEC=60
ENV
  echo "[+] Created .env (please fill OPENCLAW_TOKEN if needed)"
fi

python -m pip install --upgrade pip >/dev/null 2>&1 || true
python -m pip install -r requirements.txt >/dev/null 2>&1

nohup python bot.py > run.log 2>&1 &

echo "[+] Bot started (nohup). Logs: $PROJECT_DIR/run.log"
