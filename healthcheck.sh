#!/usr/bin/env bash
set -euo pipefail

ok=true

check() {
  local name="$1" cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "[OK] $name"
  else
    echo "[FAIL] $name"
    ok=false
  fi
}

check "Python" "python -V"
check "Pip" "python -m pip -V"
check "OpenClaw Gateway" "curl -sS http://127.0.0.1:18789/ >/dev/null"
check "OneBot WS (NapCat)" "nc -z 127.0.0.1 8080"

if [ "$ok" = true ]; then
  echo "All checks passed."
else
  echo "Some checks failed. Fix them before running the bot."
  exit 1
fi
