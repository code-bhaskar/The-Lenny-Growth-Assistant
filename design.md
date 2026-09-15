# design.md

## UI / UX principles
- **Trust first:** every answer should feel inspectable, not magical.
- **Two-surface workflow:** chat for reasoning, artifact pane for output.
- **Fast evaluator comprehension:** key controls are visible immediately—new chat, provider selector, health status, sessions, and artifact viewer.
- **Graceful degradation:** if Ollama or Anthropic is unavailable, the app should explain the problem clearly.

## Information architecture
### Left rail
- Brand / product framing
- New chat button
- Provider selector
- Health summary
- Session list

### Main chat column
- Session title and metadata
- Scrollable message timeline
- Composer with grounded-use hints
- Reindex action for the knowledge base

### Right artifact column
- Artifact viewer empty state
- Markdown render surface
- Sandboxed HTML iframe surface
- Raw artifact disclosure area for debugging and reuse

## Key interaction states
- **Cold start:** no session selected, artifact viewer empty.
- **Active chat:** messages load from persistence; latest artifact remains visible.
- **Thinking:** send button changes to “Thinking…”.
- **Grounded refusal:** assistant explains insufficient evidence instead of guessing.
- **Artifact available:** artifact opens in the right pane and remains copyable.
- **Provider degraded:** health pill reflects the issue before the user sends a message.

## Responsive behavior
- Desktop: three-part layout becomes left rail + two-pane workspace.
- Tablet/mobile: layout stacks vertically; artifact viewer remains accessible below chat.
- Controls collapse naturally without requiring a separate mobile nav.

## Accessibility considerations
- Semantic buttons, forms, and headings
- Adequate contrast for primary actions and health states
- Keyboard-accessible session list and artifact disclosure
- Plain-text message bodies preserve readability for screen readers
- No motion-heavy transitions or hover-only interactions required for core use

## Design decisions
- **Static frontend over SPA framework:** faster to ship, simpler to hand off, and enough for the evaluator workflow.
- **Visible health pill:** operational transparency matters in forward deployment.
- **Artifact raw view:** helps auditors inspect generated HTML/Markdown quickly.
- **Badge-based metadata:** route/provider/citation context remains readable without clutter.
