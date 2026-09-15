# architecture.md

## 1. System overview
The Lenny Growth Assistant is a single FastAPI application serving both:
- a JSON API for chat, sessions, health, and ingestion
- a static browser UI for the evaluator workflow

Core subsystems:
1. **Session persistence** — SQLAlchemy models backed by PostgreSQL
2. **Knowledge ingestion** — transcript downloader/parser/chunker/index builder
3. **Retrieval layer** — TF-IDF ranking over chunked transcripts
4. **Agent orchestration** — route classification + prompt assembly + provider fallback
5. **Artifact renderer** — markdown rendering or sanitized HTML iframe rendering

## 2. Component boundaries
### Backend API (`app/api`)
- Request validation via Pydantic
- Response models for sessions, messages, providers, health, and artifacts
- Structured error envelopes

### Core config/logging (`app/core`)
- Environment-driven configuration
- JSON logging

### Persistence (`app/db`)
- `chat_sessions`
- `messages`
- `artifacts`

### Services (`app/services`)
- `knowledge.py`: source sync, parsing, chunking, TF-IDF index build/search
- `conversations.py`: session lifecycle, routing, provider selection, persistence
- `artifacts.py`: markdown rendering, HTML sanitization, artifact parsing
- `agent/providers.py`: Ollama + Anthropic provider adapters
- `agent/claude_sdk_adapter.py`: optional Anthropic Claude Agent SDK path

## 3. Database schema
### `chat_sessions`
- `id` UUID string primary key
- `title`
- `user_name`
- `user_role`
- `metadata` JSON
- `created_at`
- `updated_at`

### `messages`
- `id` UUID string primary key
- `session_id` FK → `chat_sessions`
- `role` (`user` / `assistant`)
- `content`
- `route` (`user`, `qa`, `ship30`, `artifact`)
- `provider`
- `citations` JSON array
- `artifact_id` FK → `artifacts`
- `created_at`

### `artifacts`
- `id` UUID string primary key
- `session_id` FK → `chat_sessions`
- `title`
- `artifact_type` (`markdown` / `html`)
- `raw_content`
- `sanitized_content`
- `render_mode`
- `created_at`

## 4. API endpoints
- `GET /health`
- `GET /health/ready`
- `GET /api/providers`
- `GET /api/sessions`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/chat`
- `POST /api/admin/reingest`

## 5. Ingestion and retrieval flow
1. Download the transcript repository ZIP from GitHub if a local cache is absent.
2. Parse each `episodes/*/transcript.md` file.
3. Extract YAML frontmatter metadata.
4. Chunk transcript bodies into overlapping sections.
5. Persist a processed manifest and TF-IDF index to disk.
6. At query time, rank chunks by cosine similarity.
7. Pass top chunks into the agent prompt with source markers (`[S1]`, `[S2]`, etc.).
8. Return citations derived directly from retrieval metadata.

### Refresh behavior
- `POST /api/admin/reingest` rebuilds the processed index.
- On startup, `INGEST_ON_STARTUP=true` can force a refresh.
- If remote download fails, the app falls back to bundled sample transcripts so the UI remains evaluable.

## 6. Agent routing
Routing is intentionally explicit rather than fully autonomous:
- **Q&A route:** default grounded question answering
- **Ship 30 route:** dedicated long-form essay skill with encoded writing principles
- **Artifact route:** markdown or HTML/CSS generation for current conversation context

This keeps behavior predictable and easier to audit than a general-purpose tool-using agent.

## 7. Model toggle and fallback behavior
Configured provider options:
- `ollama` for the mandatory local demo
- `anthropic` for cloud inference

Fallback logic:
- Use the requested or default provider if available.
- If unavailable, fall back to the other provider automatically.
- If neither is available, return a structured 503 error.

The Anthropic path supports two modes:
- direct Messages API
- optional Claude Agent SDK adapter when `ENABLE_CLAUDE_AGENT_SDK=true`

## 8. Security model for artifacts
Generated HTML is treated as untrusted.

Controls:
1. Strip obviously dangerous tags (`script`, `iframe`, `object`, `embed`, `form`, `link`, `meta`).
2. Remove event handler attributes (`onclick`, etc.) and `javascript:` URLs.
3. Wrap output in a strict CSP document.
4. Render HTML only inside an empty-permission sandboxed iframe.
5. Do not execute JavaScript.

Trade-off:
- This allows rich layout and CSS but still permits visual spoofing inside the iframe. That is acceptable for a take-home artifact viewer but would merit stronger policy enforcement in production.

## 9. Deployment topology
### Recommended local stack
- `app` container: FastAPI + static frontend
- `db` container: PostgreSQL 16
- `ollama` container: local model runtime

### Data volumes
- PostgreSQL data volume
- Ollama model cache volume
- App `data/` directory for transcript cache and retrieval index

## 10. Observability and resilience
- JSON logs via `python-json-logger`
- Health endpoints for DB/knowledge/provider checks
- Tenacity retries for provider calls
- Graceful weak-retrieval refusal path
- Explicit error messages for missing API keys, DB issues, and Ollama unavailability
