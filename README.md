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
ANTHROPIC_API_KEY=
PI_AGENT_BACKEND=node
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
