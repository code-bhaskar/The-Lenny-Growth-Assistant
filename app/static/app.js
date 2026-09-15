const state = {
  sessions: [],
  currentSessionId: null,
  currentArtifact: null,
  providers: [],
};

const els = {
  newChatButton: document.getElementById('new-chat-button'),
  refreshSessionsButton: document.getElementById('refresh-sessions-button'),
  reindexButton: document.getElementById('reindex-button'),
  providerSelect: document.getElementById('provider-select'),
  healthPill: document.getElementById('health-pill'),
  sessionList: document.getElementById('session-list'),
  sessionTitle: document.getElementById('session-title'),
  sessionMeta: document.getElementById('session-meta'),
  messages: document.getElementById('messages'),
  composer: document.getElementById('composer'),
  messageInput: document.getElementById('message-input'),
  sendButton: document.getElementById('send-button'),
  artifactEmpty: document.getElementById('artifact-empty'),
  artifactView: document.getElementById('artifact-view'),
  artifactTitle: document.getElementById('artifact-title'),
  artifactType: document.getElementById('artifact-type'),
  artifactMarkdown: document.getElementById('artifact-markdown'),
  artifactIframe: document.getElementById('artifact-iframe'),
  artifactRawContent: document.getElementById('artifact-raw-content'),
  copyArtifactButton: document.getElementById('copy-artifact-button'),
  messageTemplate: document.getElementById('message-template'),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail || payload.error || 'Request failed');
  }
  return response.json();
}

function setHealthPill(text, status = 'ok') {
  els.healthPill.textContent = text;
  els.healthPill.className = `health-pill ${status}`;
}

function formatDate(value) {
  if (!value) return 'unknown';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function renderSessions() {
  els.sessionList.innerHTML = '';
  if (!state.sessions.length) {
    els.sessionList.innerHTML = '<p class="hint">No sessions yet. Start a new chat.</p>';
    return;
  }

  state.sessions.forEach((session) => {
    const button = document.createElement('button');
    button.className = `session-button ${session.id === state.currentSessionId ? 'active' : ''}`;
    button.innerHTML = `
      <div class="session-title">${escapeHtml(session.title || 'Untitled chat')}</div>
      <div class="session-meta-small">${escapeHtml(session.user_name)} · ${formatDate(session.updated_at || session.created_at)}</div>
    `;
    button.addEventListener('click', () => loadSession(session.id));
    els.sessionList.appendChild(button);
  });
}

function renderMessages(messages) {
  els.messages.innerHTML = '';
  if (!messages.length) {
    els.messages.innerHTML = '<p class="hint">Start by asking a product or growth question grounded in Lenny’s transcripts.</p>';
    return;
  }

  messages.forEach((message) => {
    const node = els.messageTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector('.message-role').textContent = message.role.toUpperCase();
    node.querySelector('.message-route').textContent = message.route;
    node.querySelector('.message-provider').textContent = message.provider;
    node.querySelector('.message-body').textContent = message.content;

    const citationsContainer = node.querySelector('.citations');
    if (message.citations?.length) {
      message.citations.forEach((citation) => {
        const card = document.createElement('div');
        card.className = 'citation-card';
        const link = citation.youtube_url
          ? `<div><a href="${citation.youtube_url}" target="_blank" rel="noreferrer">Open source</a></div>`
          : '';
        card.innerHTML = `
          <strong>${escapeHtml(citation.transcript_title)}</strong>
          <div>${escapeHtml(citation.guest || 'Unknown guest')} · ${escapeHtml(citation.publish_date || 'Unknown date')} · score ${citation.score ?? 'n/a'}</div>
          <div>${escapeHtml(citation.snippet)}</div>
          <div>${escapeHtml(citation.source_path)}</div>
          ${link}
        `;
        citationsContainer.appendChild(card);
      });
    }

    if (message.artifact) {
      const openButton = document.createElement('button');
      openButton.className = 'ghost-button';
      openButton.textContent = `Open artifact: ${message.artifact.title}`;
      openButton.addEventListener('click', () => renderArtifact(message.artifact));
      citationsContainer.appendChild(openButton);
      state.currentArtifact = message.artifact;
    }

    els.messages.appendChild(node);
  });
  els.messages.scrollTop = els.messages.scrollHeight;
  if (state.currentArtifact) renderArtifact(state.currentArtifact);
}

function renderArtifact(artifact) {
  state.currentArtifact = artifact;
  els.artifactEmpty.classList.add('hidden');
  els.artifactView.classList.remove('hidden');
  els.artifactTitle.textContent = artifact.title;
  els.artifactType.textContent = artifact.artifact_type;
  els.artifactRawContent.textContent = artifact.raw_content;

  if (artifact.render_mode === 'html') {
    els.artifactMarkdown.classList.add('hidden');
    els.artifactIframe.classList.remove('hidden');
    els.artifactIframe.srcdoc = artifact.sanitized_content;
  } else {
    els.artifactIframe.classList.add('hidden');
    els.artifactMarkdown.classList.remove('hidden');
    els.artifactMarkdown.innerHTML = artifact.sanitized_content;
  }
}

function clearArtifact() {
  state.currentArtifact = null;
  els.artifactEmpty.classList.remove('hidden');
  els.artifactView.classList.add('hidden');
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function refreshHealth() {
  try {
    const health = await api('/health');
    const text = `DB: ${health.database} · KB: ${health.knowledge_base} · Provider: ${health.llm_provider}`;
    setHealthPill(text, health.status);
  } catch (error) {
    setHealthPill(`Health check failed: ${error.message}`, 'error');
  }
}

async function loadProviders() {
  const data = await api('/api/providers');
  state.providers = data.providers;
  els.providerSelect.innerHTML = '';
  data.providers.forEach((provider) => {
    const option = document.createElement('option');
    option.value = provider.key;
    option.textContent = `${provider.label}${provider.available ? '' : ' (unavailable)'}`;
    option.disabled = !provider.available;
    option.selected = provider.selected;
    els.providerSelect.appendChild(option);
  });
}

async function loadSessions() {
  state.sessions = await api('/api/sessions');
  renderSessions();
  if (!state.currentSessionId && state.sessions[0]) {
    await loadSession(state.sessions[0].id);
  }
}

async function createSession() {
  const session = await api('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ user: { user_name: 'Evaluator', user_role: 'Growth / Product' } }),
  });
  state.currentSessionId = session.id;
  clearArtifact();
  await loadSessions();
  await loadSession(session.id);
}

async function loadSession(sessionId) {
  const session = await api(`/api/sessions/${sessionId}`);
  state.currentSessionId = session.id;
  state.currentArtifact = session.messages.findLast((message) => message.artifact)?.artifact || null;
  els.sessionTitle.textContent = session.title;
  els.sessionMeta.textContent = `${session.user_name}${session.user_role ? ` · ${session.user_role}` : ''} · created ${formatDate(session.created_at)}`;
  renderMessages(session.messages);
  if (!state.currentArtifact) clearArtifact();
  renderSessions();
}

async function sendMessage(event) {
  event.preventDefault();
  if (!state.currentSessionId) {
    await createSession();
  }
  const content = els.messageInput.value.trim();
  if (!content) return;

  els.sendButton.disabled = true;
  els.sendButton.textContent = 'Thinking…';
  try {
    const payload = {
      session_id: state.currentSessionId,
      content,
      provider: els.providerSelect.value || null,
    };
    els.messageInput.value = '';
    await api('/api/chat', { method: 'POST', body: JSON.stringify(payload) });
    await loadSessions();
    await loadSession(state.currentSessionId);
    await refreshHealth();
  } catch (error) {
    alert(error.message);
  } finally {
    els.sendButton.disabled = false;
    els.sendButton.textContent = 'Send';
  }
}

async function reindexKnowledgeBase() {
  els.reindexButton.disabled = true;
  els.reindexButton.textContent = 'Reindexing…';
  try {
    const data = await api('/api/admin/reingest', { method: 'POST' });
    alert(`Indexed ${data.transcripts_indexed} transcripts into ${data.chunks_indexed} chunks.`);
    await refreshHealth();
  } catch (error) {
    alert(error.message);
  } finally {
    els.reindexButton.disabled = false;
    els.reindexButton.textContent = 'Reindex transcripts';
  }
}

async function copyArtifact() {
  if (!state.currentArtifact) return;
  await navigator.clipboard.writeText(state.currentArtifact.raw_content);
  els.copyArtifactButton.textContent = 'Copied';
  setTimeout(() => {
    els.copyArtifactButton.textContent = 'Copy raw';
  }, 1200);
}

els.newChatButton.addEventListener('click', createSession);
els.refreshSessionsButton.addEventListener('click', loadSessions);
els.reindexButton.addEventListener('click', reindexKnowledgeBase);
els.composer.addEventListener('submit', sendMessage);
els.copyArtifactButton.addEventListener('click', copyArtifact);

(async function init() {
  await refreshHealth();
  await loadProviders();
  await loadSessions();
})();
