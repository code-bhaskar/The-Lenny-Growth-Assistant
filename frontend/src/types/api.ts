export type ProviderKey = 'ollama' | 'anthropic';

export interface Citation {
  source_id: string;
  transcript_title: string;
  source_path: string;
  source_url?: string | null;
  guest?: string | null;
  publish_date?: string | null;
  snippet: string;
  chunk_index: number;
  score?: number | null;
}

export interface ArtifactView {
  id: string;
  session_id: string;
  message_id?: string | null;
  title: string;
  type: 'markdown' | 'html';
  content: string;
  sanitized_content: string;
  render_mode: 'markdown' | 'html';
  created_at: string;
}

export interface MessageMetadata {
  route: string;
  provider: ProviderKey;
  model?: string | null;
  retrieval_summary?: Record<string, unknown>;
  fallback_note?: string | null;
  artifact_ids?: string[];
  artifact_word_count?: number | null;
  runtime_backend?: string | null;
}

export interface MessageView {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  metadata: MessageMetadata;
  citations: Citation[];
  artifacts: ArtifactView[];
  created_at: string;
}

export interface SessionView {
  id: string;
  title: string;
  user_metadata: Record<string, unknown>;
  created_at: string;
  updated_at?: string | null;
}

export interface SessionDetailView extends SessionView {
  messages: MessageView[];
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  database: string;
  knowledge_base: string;
  agent_layer: string;
  selected_provider: string;
  details: Record<string, unknown>;
}

export interface ProviderStatus {
  key: ProviderKey;
  label: string;
  selected: boolean;
  available: boolean;
  model?: string | null;
  reason?: string | null;
}

export interface ProvidersResponse {
  providers: ProviderStatus[];
}

export interface IngestionResponse {
  status: 'ok';
  sources_indexed: number;
  chunks_indexed: number;
  source_dir: string;
  timestamp: string;
}
