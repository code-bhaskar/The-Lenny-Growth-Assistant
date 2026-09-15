# The Lenny Growth Assistant

A full-stack, grounded AI assistant for product and growth teams using Lenny's Podcast transcripts.

## What it does
- Ingests transcripts from the [ChatPRD/lennys-podcast-transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts) repository
- Answers product and growth questions with transcript-backed citations
- Supports a dedicated Ship 30 for 30-style long-form writing skill
- Generates Markdown or HTML/CSS artifacts and renders them beside the chat
- Persists sessions, messages, timestamps, and user metadata in PostgreSQL
- Lets evaluators switch between **Ollama (local)** and **Anthropic Claude (cloud)** without changing code

## Demo path
### Recommended one-command startup
```bash
cp .env.example .env
docker compose up --build
```

Then open:
- App: http://localhost:8000
- API docs: http://localhost:8000/docs

> Notes
> - The first startup may take longer because the app can download the transcript repository and Ollama may need to pull the configured model.
> - Default local model: `qwen2.5:3b` for a lighter, evaluator-friendly demo footprint.

## Architecture overview
### Backend
- **FastAPI** API + static asset host
- **SQLAlchemy** persistence layer
- **PostgreSQL** for sessions/messages/artifacts
- **TF-IDF retrieval** over chunked transcripts for grounded RAG
- **Provider abstraction** for Ollama and Anthropic
- **Optional Claude Agent SDK path** for Anthropic-backed agent execution

### Frontend
- Lightweight static HTML/CSS/JS
- Session list + chat panel + artifact viewer
- Markdown renderer and sandboxed HTML iframe viewer

### Retrieval strategy
- Download transcript repository ZIP on demand
- Parse transcript frontmatter + content
- Chunk transcript bodies with overlap
- Build a TF-IDF index saved to `data/processed/`
- Retrieve top chunks for each user question
- Pass retrieved snippets into the selected model with strict grounding instructions

## Project structure
```text
app/
  api/                 # FastAPI routes, schemas, errors
  core/                # settings + logging
  db/                  # SQLAlchemy models + session helpers
  services/            # ingestion, retrieval, routing, providers, artifacts
  static/              # chat UI and artifact viewer
agent-transcripts/     # condensed build log / handoff notes
data/samples/          # bundled fallback transcripts for tests/offline smoke runs
docs/                  # manual UI test plan
```

## Prerequisites
### Option A — Docker Compose (recommended)
- Docker
- Docker Compose

### Option B — Local Python + Postgres + Ollama
- Python 3.11+
- PostgreSQL 16+
- Ollama installed locally

## Environment variables
Copy `.env.example` to `.env` and adjust as needed.

### Required for local Ollama demo
- `DATABASE_URL`
- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`

### Optional for cloud fallback
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `ENABLE_CLAUDE_AGENT_SDK=true` to route Anthropic requests through the Claude Agent SDK adapter

### Important operational flags
- `INGEST_ON_STARTUP=true` — rebuild transcript index at app boot
- `OLLAMA_AUTO_PULL=true` — ask Ollama to pull the configured model automatically
- `RETRIEVAL_SCORE_THRESHOLD=0.08` — controls when the assistant refuses weakly grounded answers

## Local setup without Docker
```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Optional only if you want Anthropic Agent SDK mode:
# pip install -r requirements-optional.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

If you want PostgreSQL locally, update `DATABASE_URL` accordingly.

## Ollama setup
### If using Docker Compose
The `ollama` service starts automatically. The app will call the Ollama pull endpoint when `OLLAMA_AUTO_PULL=true`.

### If using host Ollama
```bash
ollama serve
ollama pull qwen2.5:3b
```
Then set:
```env
OLLAMA_BASE_URL=http://localhost:11434
```

### Suggested alternative models
- `qwen2.5:7b`
- `llama3.1:8b`

## Anthropic / Claude setup
Set:
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here
```

Optional Agent SDK mode:
```env
ENABLE_CLAUDE_AGENT_SDK=true
CLAUDE_AGENT_SDK_MODEL=claude-sonnet-4-5
```

This project includes an **optional** Claude Agent SDK adapter. If enabled, the Anthropic path attempts to call the Agent SDK instead of the raw Messages API. If the SDK is unavailable or the key is missing, the app reports that clearly and can fall back to Ollama if available.

## API summary
### Health
- `GET /health`
- `GET /health/ready`

### Sessions
- `GET /api/sessions`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}`

### Chat
- `POST /api/chat`

Example:
```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "<SESSION_ID>",
    "content": "What do the transcripts say about product-market fit?",
    "provider": "ollama"
  }'
```

### Reindex transcripts
- `POST /api/admin/reingest`

## Grounding behavior
- Retrieved transcript chunks are inserted into the prompt with explicit source markers (`[S1]`, `[S2]`, ...).
- Citations returned to the UI come directly from the retrieval layer.
- If retrieval is weak, the assistant refuses instead of guessing.
- Artifact generation is also grounded: if retrieval is weak, the assistant declines to generate the artifact.

## Ship 30 for 30 skill
The Ship 30 route is not a one-off prompt. It encodes reusable writing principles in a dedicated prompt:
- sharp hook
- one clear narrative arc
- short paragraphs
- skimmable headings and bullets
- selective bold emphasis
- concrete takeaway
- explicit grounding in transcript sources

## Artifact viewer security
Generated HTML is treated as untrusted.

The viewer:
- strips scripts, forms, iframes, embeds, and inline event handlers
- removes `javascript:` URLs
- wraps the result in a strict Content Security Policy
- renders HTML only in a sandboxed iframe

Markdown is rendered to sanitized HTML before display.

## Tests
Run:
```bash
source .venv/bin/activate
pytest
```

Current automated coverage focuses on:
- health endpoint
- session creation + persistence
- grounded chat behavior
- Ship 30 artifact generation
- HTML sanitization
- provider fallback
- weak retrieval refusal behavior

## Manual test plan
See [`docs/manual-test-plan.md`](docs/manual-test-plan.md).

## Troubleshooting
### Ollama unavailable
Symptoms:
- Provider shown as unavailable
- Chat requests return a provider error or automatic fallback message

Fixes:
- Ensure `ollama serve` is running or the Docker `ollama` service is up
- Pull the configured model manually
- Verify `OLLAMA_BASE_URL`

### Database connection failure
Symptoms:
- `/health` shows `database=unavailable`
- Session creation fails

Fixes:
- Start PostgreSQL
- Check `DATABASE_URL`
- If using Docker Compose, confirm `db` is healthy

### Empty retrieval results
Symptoms:
- Assistant refuses to answer

Fixes:
- Trigger `POST /api/admin/reingest`
- Verify transcript download access
- Confirm `data/processed/chunks.json` and `tfidf_index.joblib` exist

### Anthropic path unavailable
Symptoms:
- Provider marked unavailable

Fixes:
- Add `ANTHROPIC_API_KEY`
- Disable `ENABLE_CLAUDE_AGENT_SDK` if you want the raw Messages API path
- Or install/verify the Claude Agent SDK in your environment

## Handoff / extension notes
Good next steps for a production deployment:
- add migrations with Alembic
- move ingestion to a background worker
- add streaming responses over SSE/WebSockets
- improve retriever quality with embeddings or hybrid search
- add auth and workspace-level access controls
- add richer observability for prompt traces and latency metrics

## Deliverables map
- `README.md` — setup, architecture, tests, troubleshooting
- `PRD.md` — discovery brief, assumptions, scope, risks, acceptance criteria
- `design.md` — UX decisions and accessibility
- `architecture.md` — system boundaries, schema, APIs, security, topology
- `agent-transcripts/` — condensed development log including a failed attempt and correction
- `docs/manual-test-plan.md` — evaluator UI checks

## Demo video
A camera-on 2–3 minute demo video is still required for final submission. Suggested structure:
1. Problem framing
2. Show grounded Q&A
3. Show Ship 30 essay generation
4. Show HTML artifact viewer
5. Show Ollama configuration in `.env`
6. Close with one explicit technical trade-off (TF-IDF simplicity vs. richer semantic retrieval)
