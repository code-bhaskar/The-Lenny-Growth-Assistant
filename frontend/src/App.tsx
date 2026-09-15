import { useEffect, useMemo, useState } from 'react';

import { ArtifactViewer } from './components/ArtifactViewer';
import { ChatWindow } from './components/ChatWindow';
import { Composer } from './components/Composer';
import { ProviderStatusPanel } from './components/ProviderStatus';
import { SessionSidebar } from './components/SessionSidebar';
import { api } from './lib/api';
import type {
  ArtifactView,
  HealthResponse,
  ProviderKey,
  ProviderStatus,
  SessionDetailView,
  SessionView,
} from './types/api';

export default function App() {
  const [sessions, setSessions] = useState<SessionView[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [currentSession, setCurrentSession] = useState<SessionDetailView | null>(null);
  const [currentArtifact, setCurrentArtifact] = useState<ArtifactView | null>(null);
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<ProviderKey>('ollama');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const currentMessageForArtifact = useMemo(() => {
    if (!currentSession) return null;
    const assistantMessages = currentSession.messages.filter((message) => message.role === 'assistant');
    return assistantMessages[assistantMessages.length - 1] ?? null;
  }, [currentSession]);

  useEffect(() => {
    void bootstrap();
  }, []);

  async function bootstrap() {
    await Promise.all([loadHealth(), loadProviders(), loadSessions()]);
  }

  async function loadHealth() {
    setHealth(await api.health());
  }

  async function loadProviders() {
    const data = await api.providers();
    setProviders(data);
    const selected = data.find((provider) => provider.selected)?.key;
    if (selected) setSelectedProvider(selected);
  }

  async function loadSessions() {
    const data = await api.listSessions();
    setSessions(data);
    if (!currentSessionId && data.length) {
      await openSession(data[0].id);
    }
  }

  async function createSession() {
    const session = await api.createSession({ user_metadata: { user_name: 'Evaluator', user_role: 'Product / Growth' } });
    setCurrentSessionId(session.id);
    setCurrentArtifact(null);
    await loadSessions();
    await openSession(session.id);
  }

  async function openSession(sessionId: string) {
    const session = await api.getSession(sessionId);
    setCurrentSessionId(session.id);
    setCurrentSession(session);
    const allArtifacts = session.messages.flatMap((message) => message.artifacts);
    const latestArtifact = allArtifacts[allArtifacts.length - 1] ?? null;
    setCurrentArtifact(latestArtifact);
  }

  async function sendMessage() {
    if (!input.trim()) return;
    const sessionId = currentSessionId ?? (await api.createSession({ user_metadata: { user_name: 'Evaluator' } })).id;
    if (!currentSessionId) setCurrentSessionId(sessionId);

    setLoading(true);
    try {
      await api.postMessage(sessionId, input, selectedProvider);
      setInput('');
      await loadSessions();
      await openSession(sessionId);
      await loadHealth();
    } finally {
      setLoading(false);
    }
  }

  async function generateArtifact(type: 'markdown' | 'html') {
    if (!currentSessionId) {
      await createSession();
      return;
    }
    if (!input.trim()) return;
    setLoading(true);
    try {
      const artifact = await api.createArtifact({
        session_id: currentSessionId,
        instruction: input,
        type,
        provider: selectedProvider,
        message_id: currentMessageForArtifact?.id ?? null,
      });
      setCurrentArtifact(artifact);
      setInput('');
      await loadSessions();
      await openSession(currentSessionId);
    } finally {
      setLoading(false);
    }
  }

  async function copyArtifact() {
    if (!currentArtifact) return;
    await navigator.clipboard.writeText(currentArtifact.content);
  }

  async function reingest() {
    setLoading(true);
    try {
      const result = await api.reingest();
      alert(`Indexed ${result.sources_indexed} sources and ${result.chunks_indexed} chunks.`);
      await loadHealth();
    } finally {
      setLoading(false);
    }
  }

  async function openArtifact(artifactId: string) {
    setCurrentArtifact(await api.getArtifact(artifactId));
  }

  return (
    <div className="shell">
      <SessionSidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onCreate={() => void createSession()}
        onRefresh={() => void loadSessions()}
        onSelect={(id) => void openSession(id)}
      />

      <main className="workspace">
        <div className="chat-column">
          <ProviderStatusPanel
            providers={providers}
            selectedProvider={selectedProvider}
            health={health}
            onProviderChange={setSelectedProvider}
            onReingest={() => void reingest()}
          />
          <ChatWindow session={currentSession} onOpenArtifact={(id) => void openArtifact(id)} />
          <Composer
            value={input}
            loading={loading}
            onChange={setInput}
            onSend={() => void sendMessage()}
            onCreateMarkdownArtifact={() => void generateArtifact('markdown')}
            onCreateHtmlArtifact={() => void generateArtifact('html')}
          />
        </div>
        <ArtifactViewer artifact={currentArtifact} onCopy={() => void copyArtifact()} />
      </main>
    </div>
  );
}
