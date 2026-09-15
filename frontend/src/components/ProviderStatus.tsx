import type { HealthResponse, ProviderKey, ProviderStatus } from '../types/api';

interface Props {
  providers: ProviderStatus[];
  selectedProvider: ProviderKey;
  health: HealthResponse | null;
  onProviderChange: (provider: ProviderKey) => void;
  onReingest: () => void;
}

export function ProviderStatusPanel({
  providers,
  selectedProvider,
  health,
  onProviderChange,
  onReingest,
}: Props) {
  return (
    <div className="panel toolbar-panel">
      <div className="provider-row">
        <label htmlFor="provider-select">Model provider</label>
        <select
          id="provider-select"
          value={selectedProvider}
          onChange={(event) => onProviderChange(event.target.value as ProviderKey)}
        >
          {providers.map((provider) => (
            <option key={provider.key} value={provider.key} disabled={!provider.available}>
              {provider.label}
              {provider.available ? '' : ' (unavailable)'}
            </option>
          ))}
        </select>
      </div>

      <div className={`health-pill ${health?.status ?? 'degraded'}`}>
        {health
          ? `DB: ${health.database} · KB: ${health.knowledge_base} · Agent: ${health.agent_layer}`
          : 'Checking system…'}
      </div>

      <button className="ghost-button" onClick={onReingest}>
        Reindex transcripts
      </button>
    </div>
  );
}
