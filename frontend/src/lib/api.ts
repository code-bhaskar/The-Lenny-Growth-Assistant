import type {
  ArtifactView,
  HealthResponse,
  IngestionResponse,
  MessageView,
  ProviderKey,
  ProvidersResponse,
  SessionDetailView,
  SessionView,
} from '../types/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail || payload.error || 'Request failed');
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>('/health'),
  providers: async () => (await request<ProvidersResponse>('/api/providers')).providers,
  listSessions: () => request<SessionView[]>('/api/sessions'),
  createSession: (payload?: { title?: string | null; user_metadata?: Record<string, unknown> }) =>
    request<SessionView>('/api/sessions', {
      method: 'POST',
      body: JSON.stringify(payload || { user_metadata: { user_name: 'Evaluator' } }),
    }),
  getSession: (sessionId: string) => request<SessionDetailView>(`/api/sessions/${sessionId}`),
  listMessages: (sessionId: string) => request<MessageView[]>(`/api/sessions/${sessionId}/messages`),
  postMessage: (sessionId: string, content: string, provider?: ProviderKey | null) =>
    request<MessageView>(`/api/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, provider: provider ?? null }),
    }),
  reingest: () => request<IngestionResponse>('/api/ingestion', { method: 'POST' }),
  createArtifact: (payload: {
    session_id: string;
    instruction: string;
    type: 'markdown' | 'html';
    provider?: ProviderKey | null;
    message_id?: string | null;
  }) =>
    request<ArtifactView>('/api/artifacts', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getArtifact: (artifactId: string) => request<ArtifactView>(`/api/artifacts/${artifactId}`),
};
