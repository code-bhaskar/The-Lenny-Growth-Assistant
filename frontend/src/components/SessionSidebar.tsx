import type { SessionView } from '../types/api';

interface Props {
  sessions: SessionView[];
  currentSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onCreate: () => void;
  onRefresh: () => void;
}

function formatDate(value?: string | null) {
  if (!value) return 'unknown';
  return new Date(value).toLocaleString();
}

export function SessionSidebar({ sessions, currentSessionId, onSelect, onCreate, onRefresh }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">L</div>
        <div>
          <h1>The Lenny Growth Assistant</h1>
          <p>Grounded product and growth research</p>
        </div>
      </div>

      <div className="panel">
        <button className="primary-button" onClick={onCreate}>
          + New Chat
        </button>
      </div>

      <div className="panel panel-grow">
        <div className="panel-header">
          <h2>Sessions</h2>
          <button className="ghost-button" onClick={onRefresh}>
            Refresh
          </button>
        </div>
        <div className="session-list">
          {!sessions.length ? <p className="muted">No sessions yet.</p> : null}
          {sessions.map((session) => (
            <button
              key={session.id}
              className={`session-button ${session.id === currentSessionId ? 'active' : ''}`}
              onClick={() => onSelect(session.id)}
            >
              <div className="session-title">{session.title}</div>
              <div className="session-meta-small">
                {String(session.user_metadata.user_name ?? 'Evaluator')} · {formatDate(session.updated_at || session.created_at)}
              </div>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
