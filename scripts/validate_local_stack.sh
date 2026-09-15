#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/logs"

if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi
source "$ROOT/.venv/bin/activate"
pip install -r "$ROOT/backend/requirements.txt"

pushd "$ROOT/frontend" >/dev/null
npm install
popd >/dev/null

BACKEND_LOG="$ROOT/logs/local-backend.log"
FRONTEND_LOG="$ROOT/logs/local-frontend.log"
DB_PATH="$ROOT/local-validation.db"
LOCAL_API_PORT="${LOCAL_API_PORT:-8011}"
LOCAL_FRONTEND_PORT="${LOCAL_FRONTEND_PORT:-3001}"
rm -f "$DB_PATH"

cleanup() {
  set +e
  if [ -n "${FRONTEND_PID:-}" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  if [ -n "${BACKEND_PID:-}" ]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

pushd "$ROOT/backend" >/dev/null
PYTHONPATH=. ENV=development \
DATABASE_URL="sqlite:///$DB_PATH" \
TRANSCRIPT_CACHE_DIR="$ROOT/data/raw/local-validation-transcripts" \
TRANSCRIPT_FIXTURE_DIR="$ROOT/data/samples" \
INGEST_ON_STARTUP=true \
LLM_PROVIDER=ollama \
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}" \
PI_AGENT_BACKEND="${PI_AGENT_BACKEND:-in_process}" \
FRONTEND_ORIGIN="http://127.0.0.1:${LOCAL_FRONTEND_PORT}" \
"$ROOT/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$LOCAL_API_PORT" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
popd >/dev/null

pushd "$ROOT/frontend" >/dev/null
VITE_PROXY_TARGET="http://127.0.0.1:${LOCAL_API_PORT}" npm run dev -- --host 127.0.0.1 --port "$LOCAL_FRONTEND_PORT" >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
popd >/dev/null

python "$ROOT/scripts/wait_for_http.py" "http://127.0.0.1:${LOCAL_API_PORT}/health" --timeout 180
python "$ROOT/scripts/wait_for_http.py" "http://127.0.0.1:${LOCAL_FRONTEND_PORT}/" --timeout 180 --expect-text "The Lenny Growth Assistant"
python "$ROOT/scripts/smoke_test_stack.py" --api-base "http://127.0.0.1:${LOCAL_API_PORT}" --frontend-base "http://127.0.0.1:${LOCAL_FRONTEND_PORT}"

echo "Local stack validation passed."
