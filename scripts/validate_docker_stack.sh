#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for docker stack validation" >&2
  exit 1
fi

ENV_FILE=".env.validation.generated"
cp .env.example "$ENV_FILE"

if [ "${VALIDATE_WITH_OLLAMA:-0}" != "1" ]; then
  python - <<'PY'
from pathlib import Path
path = Path('.env.validation.generated')
text = path.read_text()
text = text.replace('PI_AGENT_BACKEND=node', 'PI_AGENT_BACKEND=in_process')
text = text.replace('OLLAMA_AUTO_PULL=true', 'OLLAMA_AUTO_PULL=false')
path.write_text(text)
PY
fi

cleanup() {
  if [ "${KEEP_STACK_UP:-0}" != "1" ]; then
    docker compose --env-file "$ENV_FILE" down >/dev/null 2>&1 || true
  fi
  rm -f "$ENV_FILE"
}
trap cleanup EXIT

docker compose --env-file "$ENV_FILE" up -d --build
python scripts/wait_for_http.py "http://127.0.0.1:8000/health" --timeout 300
python scripts/wait_for_http.py "http://127.0.0.1:3000/" --timeout 300 --expect-text "The Lenny Growth Assistant"
python scripts/smoke_test_stack.py --api-base "http://127.0.0.1:8000" --frontend-base "http://127.0.0.1:3000"

echo "Docker stack validation passed."
