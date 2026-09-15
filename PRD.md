# The Lenny Growth Assistant — Product Requirements Document

## Product overview
The Lenny Growth Assistant is a full-stack AI-powered conversational application that turns Lenny's Podcast transcripts into a grounded internal assistant for product and growth teams.

## Discovery brief
### User and problem
Primary user: a product, growth, or PMM teammate who needs fast, trustworthy synthesis from Lenny's transcripts without manually searching long documents or writing prompts.

### Success metrics
- Grounded answer success rate for evaluation prompts
- Reliable session persistence across follow-ups
- Successful artifact generation/rendering
- Local Ollama demo path works
- Fresh evaluator can run the product from the docs

### Assumptions
- Evaluator can run Docker and Ollama
- PostgreSQL is the persistence layer
- Full auth is out of scope for the MVP
- Local Ollama quality is acceptable for the demo

### Scope included
- React + TypeScript frontend
- FastAPI backend
- Pi Coding Agent agent layer
- PostgreSQL persistence
- transcript ingestion and retrieval
- Ship 30 skill
- Markdown and HTML/CSS artifacts
- artifact viewer with isolation/sanitization
- structured logs, tests, docs, Docker Compose

### Risks and trade-offs
- hallucination -> mitigate with retrieval grounding and refusal behavior
- local model quality -> keep provider configurable
- unsafe HTML -> sanitize and sandbox
- latency -> bounded retrieval and simple architecture

## Goals
1. Provide transcript-grounded answers.
2. Preserve independent sessions.
3. Generate reusable Ship 30-style content.
4. Generate markdown and HTML artifacts.
5. Render artifacts inside the product.
6. Support Ollama and Anthropic through configuration.

## Core flows
- new chat
- follow-up question
- unsupported question refusal
- Ship 30 content generation
- artifact generation and rendering

## Functional requirements
- `POST /api/sessions/{session_id}/messages` persists conversation turns
- `GET /api/sessions/{session_id}/messages` returns ordered history
- `POST /api/ingestion` refreshes transcript data
- `POST /api/artifacts` creates a grounded artifact
- sources are visible in grounded responses
- HTML artifacts are treated as untrusted

## Acceptance criteria
- FastAPI backend works
- React + TypeScript frontend works
- Pi Coding Agent is the primary agent layer
- Ollama works as local provider
- Anthropic works as cloud provider when configured
- PostgreSQL stores sessions, messages, sources, transcript chunks, and artifacts
- artifact viewer renders beside chat
- tests cover critical API, retrieval, routing, persistence, and artifact safety behavior
