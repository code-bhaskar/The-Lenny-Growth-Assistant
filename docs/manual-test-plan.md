# Manual test plan

## Preconditions
- Start the stack with Docker Compose or run the app locally.
- Ensure Ollama is reachable and has the configured model pulled.
- Open `http://localhost:8000`.

## Test cases
### 1. Health visibility
- Confirm the health pill loads.
- Expected: database, knowledge base, and provider states are visible.

### 2. Session isolation
- Create Session A and ask a PMF question.
- Create Session B and ask for an HTML artifact.
- Re-open Session A.
- Expected: each session keeps its own messages and artifact history.

### 3. Grounded Q&A
- Ask: `What do Lenny's guests say about retention versus acquisition?`
- Expected: answer includes citations/snippets and avoids generic filler.

### 4. Weak-evidence refusal
- Ask: `What do the transcripts say about asteroid mining regulation?`
- Expected: assistant says it lacks grounded evidence instead of inventing an answer.

### 5. Ship 30 skill
- Ask for a `Ship 30 style essay about PMF signals and growth loops`.
- Expected: long-form markdown artifact appears in the viewer with skimmable structure.

### 6. HTML artifact viewer
- Ask for `an HTML/CSS one-pager summarizing onboarding lessons`.
- Expected: artifact renders in the iframe; raw HTML is also viewable.

### 7. Provider fallback
- Switch to Anthropic without setting an API key.
- Send a grounded prompt.
- Expected: app falls back to Ollama and tells the user what happened.

### 8. Reindexing
- Click `Reindex transcripts`.
- Expected: success message shows transcript/chunk counts and health remains green or degraded-but-explained.
