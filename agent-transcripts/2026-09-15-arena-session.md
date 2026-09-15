# Arena agent transcript (condensed)

This folder contains a condensed development log rather than a raw provider transcript.

## Goal
Build a locally runnable, evaluator-friendly AI assistant for Lenny's Podcast transcripts with grounded chat, content generation, artifacts, persistence, and handoff docs.

## Iteration log
1. **Repository discovery**
   - Confirmed the repo only contained a placeholder README.
   - Decided to build a single FastAPI app with a static frontend to optimize delivery speed and clarity.

2. **Architecture choice**
   - Chose PostgreSQL for sessions/messages/artifacts.
   - Chose TF-IDF retrieval instead of embeddings to reduce demo friction and make local startup simpler.
   - Chose Ollama + Anthropic provider abstraction with optional Claude Agent SDK path.

3. **First ingestion attempt**
   - Implemented transcript ZIP download, frontmatter parsing, chunking, and TF-IDF indexing.
   - **Failure:** YAML dates were loaded as Python `date` objects, which broke manifest JSON serialization.
   - **Fix:** normalized publish dates to strings and used `json.dumps(..., default=str)`.

4. **Artifact security pass**
   - Added markdown rendering through a sanitization step.
   - Added HTML sanitization to remove scripts, event handlers, `javascript:` URLs, and risky tags.
   - Wrapped sanitized HTML in a CSP-constrained sandboxed iframe document.

5. **Routing / skills pass**
   - Split agent behavior into `qa`, `ship30`, and `artifact` routes.
   - Encoded Ship 30 principles directly in the dedicated prompt rather than one generic prompt.

6. **Testing pass**
   - Added API tests for health, grounded chat, Ship 30 artifacts, HTML sanitization, provider fallback, and weak-retrieval refusal.
   - Result: `6 passed`.

## Known follow-ups
- Streaming responses would improve UX.
- Full production hardening would likely add migrations, background jobs, and stronger CSS sanitization.
- A richer semantic retriever could improve recall over TF-IDF.
