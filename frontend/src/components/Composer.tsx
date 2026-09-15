import { FormEvent } from 'react';

interface Props {
  value: string;
  loading: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onCreateMarkdownArtifact: () => void;
  onCreateHtmlArtifact: () => void;
}

export function Composer({
  value,
  loading,
  onChange,
  onSend,
  onCreateMarkdownArtifact,
  onCreateHtmlArtifact,
}: Props) {
  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSend();
  };

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <textarea
        rows={5}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Ask a product/growth question, request a Ship 30 essay, or ask for a markdown or HTML/CSS artifact…"
      />
      <div className="composer-actions">
        <p className="muted">
          Grounded answers cite transcript sources. Artifacts render beside the chat.
        </p>
        <div className="composer-buttons">
          <button type="button" className="ghost-button" onClick={onCreateMarkdownArtifact} disabled={loading}>
            Markdown artifact
          </button>
          <button type="button" className="ghost-button" onClick={onCreateHtmlArtifact} disabled={loading}>
            HTML/CSS artifact
          </button>
          <button type="submit" className="primary-button" disabled={loading || !value.trim()}>
            {loading ? 'Thinking…' : 'Send'}
          </button>
        </div>
      </div>
    </form>
  );
}
