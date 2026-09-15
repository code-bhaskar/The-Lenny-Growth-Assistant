# The Lenny Growth Assistant — Architecture

## Summary
The system is a full-stack application with:
- React + TypeScript frontend
- FastAPI backend
- PostgreSQL persistence
- Pi Coding Agent as the primary agent layer
- Ollama local model support
- Anthropic cloud model support
- transcript ingestion and retrieval
- markdown / HTML artifact rendering

## Topology
```text
Browser
  |
  v
React + TypeScript
  |
  v
FastAPI Backend
  |
  +--> PostgreSQL
  +--> Pi Coding Agent
  |      +--> Ollama
  |      +--> Anthropic
  |
  +--> Retrieval Layer
         +--> sources
         +--> transcript_chunks
```

## Backend components
- `backend/app/api/` — HTTP contracts and routes
- `backend/app/core/` — configuration and structured logging
- `backend/app/db/` — SQLAlchemy models and session management
- `backend/app/agent/` — Pi Coding Agent integration and provider configuration
- `backend/app/services/` — sessions, ingestion, retrieval, artifact safety

## Frontend components
- `SessionSidebar`
- `ProviderStatusPanel`
- `ChatWindow`
- `Composer`
- `ArtifactViewer`

## Data model
### sessions
- `id`
- `title`
- `user_metadata`
- `created_at`
- `updated_at`

### messages
- `id`
- `session_id`
- `role`
- `content`
- `metadata`
- `citations`
- `created_at`

### sources
- `id`
- `title`
- `url`
- `metadata`
- `created_at`
- `updated_at`

### transcript_chunks
- `id`
- `source_id`
- `chunk_index`
- `content`
- `metadata`
- `embedding` (nullable placeholder for future semantic retrieval)
- `created_at`
- `updated_at`

### artifacts
- `id`
- `session_id`
- `message_id`
- `title`
- `type`
- `content`
- `sanitized_content`
- `render_mode`
- `created_at`

## Message flow
```text
POST /api/sessions/{session_id}/messages
  -> persist user message
  -> retrieve top transcript chunks
  -> Pi agent chooses route (qa / ship30 / artifact)
  -> persist assistant message
  -> persist artifact(s) if present
  -> return assistant message payload
```

## Ingestion flow
```text
Transcript repository
  -> loader
  -> YAML metadata extraction
  -> chunker
  -> PostgreSQL sources + transcript_chunks
  -> retrieval cache build on demand
```

## Artifact security
Generated HTML is untrusted.

Controls:
- strip `script`, `iframe`, `object`, `embed`, `form`, `meta`, `link`
- strip inline event handlers and `javascript:` URLs
- wrap output in CSP-protected HTML
- render only in a sandboxed iframe

## Deployment
`docker compose up --build` starts:
- `db`
- `ollama`
- `backend`
- `frontend`
