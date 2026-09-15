# PRD — The Lenny Growth Assistant

## 1. Discovery brief

### User and problem
**Primary user:** an internal product, growth, or PMM teammate who wants quick, trustworthy synthesis from Lenny's Podcast without manually searching long transcripts.

**Core job to be done:**
- Ask nuanced product and growth questions
- Get grounded answers with source traceability
- Turn those answers into reusable content or artifacts
- Keep work inside one workflow instead of bouncing across docs, prompt playgrounds, and HTML editors

**Pain removed:** transcript search is slow, prompt quality is inconsistent, raw LLM outputs are hard to trust, and artifacts are often generated in formats that require extra tooling to inspect.

### Success metric
Primary product metric:
- **Grounded answer success rate:** at least 80% of evaluator test prompts return a source-cited answer or an explicit grounded refusal.

Operational metrics:
- Median local response time under 20 seconds on Ollama for standard Q&A
- 0 unsafe script execution events in the artifact viewer
- 100% of chats persisted with session ID, timestamp, and user metadata

### Assumptions
- The client values **reliability and evaluator clarity** over frontier-agent autonomy.
- Transcript-level grounding is more important than perfect semantic recall.
- A lightweight static frontend is acceptable if the chat and artifact UX feel polished.
- PostgreSQL is mandatory for sessions/persistence; the knowledge index may be rebuilt from source files.
- Ollama will be available locally for the recorded demo, but the app should degrade gracefully if it is not.
- Cloud access may be unavailable during evaluation, so Anthropic is optional rather than required for the happy path.

### Scope choices
**Included**
- FastAPI backend
- PostgreSQL-backed chat sessions and messages
- Ollama local inference
- Anthropic cloud provider + optional Claude Agent SDK path
- Transcript ingestion + chunking + TF-IDF retrieval
- Source citations and weak-evidence refusal behavior
- Ship 30 for 30 writing skill encoded as a distinct route
- Markdown + HTML/CSS artifact generation with in-app viewer
- Basic observability, health endpoints, tests, Docker Compose, and handoff docs

**Intentionally excluded**
- Multi-user auth and permissions
- Streaming token-by-token responses
- Background job queue for ingestion
- Fine-grained role-based access control
- Production-grade analytics dashboards
- Full HTML sanitization policy language or custom CSS parser

### Risks and trade-offs
- **Hallucination:** mitigated with retrieval-first prompts, source markers, and refusal on weak matches.
- **Latency:** local Ollama can be slow; default model is a smaller Ollama model to improve demo ergonomics.
- **Cost:** cloud inference is optional and explicit.
- **Local model quality:** smaller local models may format artifacts less reliably; the app includes parser fallbacks.
- **Data leakage:** no transcript content is sent to cloud models unless the Anthropic provider is explicitly selected.
- **Unsafe rendering:** generated HTML is treated as untrusted and rendered only after sanitization inside a sandboxed iframe.

## 2. Product requirements

### Core flows
1. User creates or opens a chat session.
2. User asks a product/growth question.
3. System retrieves transcript evidence.
4. System routes request to Q&A, Ship 30 essay, or artifact mode.
5. LLM produces a grounded response.
6. App stores session, messages, citations, timestamps, provider, and optional artifact.
7. If artifact exists, it renders beside the chat.

### Functional requirements
- Start new chat sessions with isolated context.
- Persist session metadata and messages in PostgreSQL.
- Support provider selection between Ollama and Anthropic.
- Show provider status in UI.
- Cite transcript sources in assistant responses.
- Refuse confidently when retrieval quality is weak.
- Generate markdown or HTML/CSS artifacts inside the app.
- Support a dedicated Ship 30 writing skill.

## 3. Acceptance criteria
- User can create multiple sessions and revisit them later.
- `/health` reports database, knowledge base, and provider readiness.
- Evaluator can switch providers from the UI without code changes.
- Chat responses include citations whenever grounded evidence exists.
- Weak retrieval returns a refusal instead of an invented answer.
- Ship 30 route produces a long-form markdown artifact.
- HTML artifacts render in a sandboxed iframe and strip scripts/event handlers.
- `docker compose up --build` is documented as the main startup path.

## 4. Implementation plan
1. Create FastAPI service with health endpoints and static UI.
2. Implement SQLAlchemy persistence for sessions, messages, and artifacts.
3. Add transcript ingestion, chunking, and TF-IDF retrieval.
4. Add provider abstraction for Ollama + Anthropic.
5. Add routing layer for Q&A, Ship 30, and artifact generation.
6. Build side-by-side artifact viewer with sanitization strategy.
7. Add tests, docs, and operational handoff materials.
