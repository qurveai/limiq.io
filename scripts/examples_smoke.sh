#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPRESS_DIR="$ROOT_DIR/examples/express-target"
FASTAPI_DIR="$ROOT_DIR/examples/fastapi-target"
SDK_DIR="$ROOT_DIR/packages/sdk-js"
FASTAPI_VENV_DIR="$FASTAPI_DIR/.venv-smoke"

EXPRESS_PID=""
FASTAPI_PID=""

cleanup() {
  if [[ -n "$EXPRESS_PID" ]] && kill -0 "$EXPRESS_PID" 2>/dev/null; then
    kill "$EXPRESS_PID" 2>/dev/null || true
    wait "$EXPRESS_PID" 2>/dev/null || true
  fi
  if [[ -n "$FASTAPI_PID" ]] && kill -0 "$FASTAPI_PID" 2>/dev/null; then
    kill "$FASTAPI_PID" 2>/dev/null || true
    wait "$FASTAPI_PID" 2>/dev/null || true
  fi
  rm -rf "$FASTAPI_VENV_DIR"
}
trap cleanup EXIT

wait_for_url() {
  local url="$1"
  local retries="${2:-15}"
  local delay_secs="${3:-1}"

  for i in $(seq 1 "$retries"); do
    if curl -sf "$url" >/dev/null; then
      return 0
    fi
    sleep "$delay_secs"
  done

  echo "Smoke check failed: $url not ready after $retries attempts" >&2
  return 1
}

echo "[smoke] Build SDK JS"
if command -v pnpm >/dev/null 2>&1; then
  pnpm --dir "$ROOT_DIR" --filter @limiq/sdk-js build
else
  npm --prefix "$SDK_DIR" run build
fi

echo "[smoke] Start Express target"
(
  cd "$EXPRESS_DIR"
  npm install --no-audit --no-fund --package-lock=false >/dev/null
  PORT=3001 KYA_BASE_URL=http://localhost:8000 npm run dev
) >/tmp/kya-express-smoke.log 2>&1 &
EXPRESS_PID="$!"

wait_for_url "http://localhost:3001/health" 15 1 || {
  echo "[smoke] Express health check failed" >&2
  exit 1
}

echo "[smoke] Start FastAPI target"
(
  cd "$FASTAPI_DIR"
  python -m venv "$FASTAPI_VENV_DIR"
  source "$FASTAPI_VENV_DIR/bin/activate"
  pip install -r requirements.txt >/tmp/kya-fastapi-smoke-pip.log 2>&1
  PORT=8001 KYA_BASE_URL=http://localhost:8000 uvicorn main:app --host 127.0.0.1 --port 8001
) >/tmp/kya-fastapi-smoke.log 2>&1 &
FASTAPI_PID="$!"

wait_for_url "http://localhost:8001/health" 15 1 || {
  echo "[smoke] FastAPI health check failed" >&2
  exit 1
}

echo "[smoke] Examples health checks passed"
