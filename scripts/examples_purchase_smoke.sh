#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PURCHASE_DIR="$ROOT_DIR/examples/purchase-target"
SDK_DIR="$ROOT_DIR/packages/sdk-js"

TARGET_PID=""

cleanup() {
  if [[ -n "$TARGET_PID" ]] && kill -0 "$TARGET_PID" 2>/dev/null; then
    kill "$TARGET_PID" 2>/dev/null || true
    wait "$TARGET_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

wait_for_url() {
  local url="$1"
  local retries="${2:-20}"
  local delay_secs="${3:-1}"

  for _ in $(seq 1 "$retries"); do
    if curl -sf "$url" >/dev/null; then
      return 0
    fi
    sleep "$delay_secs"
  done

  echo "Smoke check failed: $url not ready after $retries attempts" >&2
  return 1
}

if [[ -z "${KYA_BOOTSTRAP_TOKEN:-}" ]]; then
  echo "Missing required env var: KYA_BOOTSTRAP_TOKEN" >&2
  exit 1
fi

echo "[purchase-smoke] Build SDK JS"
if command -v pnpm >/dev/null 2>&1; then
  pnpm --dir "$ROOT_DIR" --filter @limiq/sdk-js build
else
  npm --prefix "$SDK_DIR" run build
fi

echo "[purchase-smoke] Start purchase-target"
(
  cd "$PURCHASE_DIR"
  npm install --no-audit --no-fund --package-lock=false >/dev/null
  PORT=3002 KYA_BASE_URL="${KYA_BASE_URL:-http://localhost:8000}" npm run dev
) >/tmp/kya-purchase-target-smoke.log 2>&1 &
TARGET_PID="$!"

wait_for_url "http://localhost:3002/health" 20 1 || {
  echo "[purchase-smoke] purchase-target health check failed" >&2
  exit 1
}

echo "[purchase-smoke] Run ALLOW + DENY demo"
(
  cd "$PURCHASE_DIR"
  KYA_BASE_URL="${KYA_BASE_URL:-http://localhost:8000}" \
  TARGET_BASE_URL="http://localhost:3002" \
  KYA_BOOTSTRAP_TOKEN="$KYA_BOOTSTRAP_TOKEN" \
  npm run demo
)

echo "[purchase-smoke] Business smoke passed"
