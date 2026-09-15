import type { MessageView, SessionDetailView } from '../types/api';

interface Props {
  session: SessionDetailView | null;
  onOpenArtifact: (artifactId: string) => void;
}

function formatDate(value?: string | null) {
  if (!value) return 'unknown';
  return new Date(value).toLocaleString();
}

export function ChatWindow({ session, onOpenArtifact }: Props) {
  return (
    <section className="chat-panel">
      <div className="chat-header">
        <div>
          <h2>{session?.title ?? 'Select or create a chat'}</h2>
          <p>
            {session
              ? `${String(session.user_metadata.user_name ?? 'Evaluator')} · created ${formatDate(session.created_at)}`
              : 'Each session keeps independent context in PostgreSQL.'}
          </p>
        </div>
      </div>

      <div className="messages">
        {!session ? <p className="muted">Start a new chat to begin.</p> : null}
        {session?.messages.map((message) => (
          <MessageCard key={message.id} message={message} onOpenArtifact={onOpenArtifact} />
        ))}
      </div>
    </section>
  );
}

function MessageCard({
  message,
  onOpenArtifact,
}: {
  message: MessageView;
  onOpenArtifact: (artifactId: string) => void;
}) {
  return (
    <article className="message-card">
      <div className="message-topline">
        <span className="badge">{message.role.toUpperCase()}</span>
        <span className="badge">{message.metadata.route}</span>
        <span className="badge">{message.metadata.provider}</span>
      </div>

      <div className="message-body">{message.content}</div>

      {message.citations.length ? (
        <div className="citations">
          {message.citations.map((citation) => (
            <div key={`${message.id}-${citation.source_id}-${citation.chunk_index}`} className="citation-card">
              <strong>{citation.transcript_title}</strong>
              <div>
                {citation.guest ?? 'Unknown guest'} · {citation.publish_date ?? 'Unknown date'} · chunk {citation.chunk_index}
              </div>
              <div>{citation.snippet}</div>
              <div>{citation.source_path}</div>
              {citation.source_url ? (
                <a href={citation.source_url} target="_blank" rel="noreferrer">
                  Open source
                </a>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {message.artifacts.length ? (
        <div className="artifact-links">
          {message.artifacts.map((artifact) => (
            <button key={artifact.id} className="ghost-button" onClick={() => onOpenArtifact(artifact.id)}>
              Open artifact: {artifact.title}
            </button>
          ))}
        </div>
      ) : null}
    </article>
  );
}
