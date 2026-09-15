# The Lenny Growth Assistant — Design Specification

## Design goals
- clear conversational UX
- visible source grounding
- visible provider state
- first-class artifact surface
- understandable loading/error states
- responsive layout

## Information architecture
```text
Application
├── Session Sidebar
├── Provider / Health Toolbar
├── Conversation Surface
└── Artifact Viewer
```

## Key decisions
- Artifacts render beside the conversation.
- Source evidence is visible in message cards.
- Model/provider state is visible at the top of the chat column.
- HTML is rendered only inside a sandboxed iframe.

## Responsive behavior
- desktop: sidebar + chat + artifact viewer
- mobile/tablet: stacked layout

## Accessibility considerations
- semantic controls
- visible labels
- keyboard-accessible buttons
- readable contrast
- loading state via disabled controls and clear button text
