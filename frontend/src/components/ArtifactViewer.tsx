import type { ArtifactView } from '../types/api';

interface Props {
  artifact: ArtifactView | null;
  onCopy: () => void;
}

export function ArtifactViewer({ artifact, onCopy }: Props) {
  if (!artifact) {
    return (
      <section className="artifact-panel">
        <div className="artifact-header">
          <h2>Artifact Viewer</h2>
          <p>Markdown renders inline. HTML is sandboxed and sanitized.</p>
        </div>
        <div className="artifact-empty">
          <h3>No artifact yet</h3>
          <p>Ask for a memo, one-pager, Ship 30 essay, or HTML/CSS artifact.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="artifact-panel">
      <div className="artifact-header">
        <h2>Artifact Viewer</h2>
        <p>Generated HTML is treated as untrusted and rendered in a sandboxed iframe.</p>
      </div>

      <div className="artifact-toolbar">
        <div>
          <strong>{artifact.title}</strong>
          <span className="badge">{artifact.type}</span>
        </div>
        <button className="ghost-button" onClick={onCopy}>
          Copy raw
        </button>
      </div>

      {artifact.render_mode === 'html' ? (
        <iframe className="artifact-iframe" sandbox="" srcDoc={artifact.sanitized_content} title={artifact.title} />
      ) : (
        <div className="artifact-markdown" dangerouslySetInnerHTML={{ __html: artifact.sanitized_content }} />
      )}

      <details className="artifact-raw">
        <summary>Show raw artifact</summary>
        <pre>{artifact.content}</pre>
      </details>
    </section>
  );
}
