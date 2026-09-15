# The Lenny Growth Assistant

A full-stack AI-powered conversational assistant grounded in Lenny's Podcast transcripts.

## Stack
- **Frontend:** React + TypeScript + Vite (`frontend/`)
- **Backend:** FastAPI (`backend/`)
- **Agent layer:** **Pi Coding Agent**
- **Persistence:** PostgreSQL for sessions, messages, sources, transcript chunks, and artifacts
- **Local model:** Ollama
- **Cloud model:** Anthropic Claude via configurable provider selection
- **Knowledge layer:** transcript ingestion + chunking + DB-backed retrieval

## Repository structure
```text
.
├── frontend/
├── backend/
├── ingestion/
├── skills/
├── docs/
├── agent-transcripts/
├── docker-compose.yml
├── .env.example
└── README.md
```

## One-command startup
```bash
cp .env.example .env
docker compose up --build
```

Open:
- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Environment
Copy `.env.example` to `.env` and adjust as needed.

Important variables:
```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/lenny_growth
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_AUTO_PULL=true
OLLAMA_STARTUP_RETRIES=8
PI_AGENT_BACKEND=node
PI_AGENT_ENABLE_BACKEND_FALLBACK=true
PI_AGENT_REQUEST_TIMEOUT_SECONDS=180
SHIP30_TARGET_WORDS=1250
SHIP30_MIN_WORDS=1100
SHIP30_MAX_WORDS=1400
ANTHROPIC_API_KEY=
INGEST_ON_STARTUP=true
FRONTEND_ORIGIN=http://localhost:3000
```

## Ollama demo path
The submitted demo is intended to run with Ollama.

Example host setup:
```bash
ollama serve
ollama pull qwen2.5:3b
```

### Runtime hardening
The backend now hardens the Pi/Ollama path by:
- checking Ollama availability and whether the configured model is actually pulled
- auto-pulling the configured model when `OLLAMA_AUTO_PULL=true`
- retrying model pull attempts with backoff
- timing out Pi agent requests cleanly with structured errors
- falling back from Pi `node` backend to `in_process` when configured
- surfacing runtime backend and artifact word count in message metadata

## API surface
```text
GET    /health
GET    /api/providers
GET    /api/sessions
POST   /api/sessions
GET    /api/sessions/{session_id}
GET    /api/sessions/{session_id}/messages
POST   /api/sessions/{session_id}/messages
POST   /api/ingestion
POST   /api/artifacts
GET    /api/artifacts/{artifact_id}
```

## Features
- grounded product and growth Q&A
- independent chat sessions
- PostgreSQL persistence
- source attribution
- dedicated Ship 30 for 30 skill
- automatic Ship 30 word-count enforcement into the configured target range
- markdown and HTML/CSS artifact generation
- in-app Artifact Viewer
- sandboxed/sanitized HTML rendering
- provider visibility and fallback behavior
- structured logs and health checks

## Backend tests
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
PYTHONPATH=. pytest
```

## Frontend build
```bash
cd frontend
npm install
npm run build
```

## Ingestion scripts
```bash
python ingestion/load_transcripts.py
python ingestion/chunk_transcripts.py
python ingestion/index_transcripts.py
python ingestion/refresh_pipeline.py
```

## End-to-end validation
### Local stack validation
Runs backend + frontend locally, waits for readiness, and executes an API/UI smoke test.
```bash
./scripts/validate_local_stack.sh
```

### Docker stack validation
Builds the compose stack, waits for readiness, and executes the same smoke test.
By default it uses `PI_AGENT_BACKEND=in_process` for a fast deterministic validation path. Set `VALIDATE_WITH_OLLAMA=1` to validate the real Ollama runtime.
```bash
./scripts/validate_docker_stack.sh
VALIDATE_WITH_OLLAMA=1 ./scripts/validate_docker_stack.sh
```

## Security
Generated HTML is treated as untrusted:
- sanitized before rendering
- scripts/forms/iframes removed
- inline event handlers removed
- rendered inside a sandboxed iframe
- CSP applied to the rendered document

## Notes
- `agent-transcripts/` contains development evidence, failure logs, and corrections.
- `skills/` contains the explicit grounded Q&A, Ship 30, and artifact skill definitions used by the agent layer.
- `data/samples/` provides fallback fixture transcripts for offline tests.
