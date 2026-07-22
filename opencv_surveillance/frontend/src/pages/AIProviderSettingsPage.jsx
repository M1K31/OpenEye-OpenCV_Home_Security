// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
//
// Cloud AI provider keys + per-task routing.
//
// Keys live in the shared ecosystem credential store (0600 on disk) behind the
// registry; this page talks only to OpenEye's admin-gated proxy. No endpoint
// ever returns a key — a configured provider shows only its last 4 characters.

import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient';
import { Button, TextField, Card, CardHeader } from '../components/universal';
import './AIProviderSettingsPage.css';

const PROVIDERS = [
  { id: 'anthropic', label: 'Claude (Anthropic)', hint: 'console.anthropic.com' },
  { id: 'openai', label: 'OpenAI', hint: 'platform.openai.com' },
  { id: 'gemini', label: 'Gemini (Google)', hint: 'aistudio.google.com' },
];

// Cloud usage is metered, so routing is per-task rather than one global switch:
// spend cloud where it earns its cost, keep high-volume work local.
const TASK_LABELS = {
  chat: { label: 'Chat', hint: 'high volume — local avoids overages' },
  security: { label: 'Security analysis', hint: 'low volume, high value' },
  embed: { label: 'Embeddings', hint: 'high volume — local recommended' },
};

function AIProviderSettingsPage() {
  const [status, setStatus] = useState(null);
  const [routing, setRouting] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [busy, setBusy] = useState(null);
  const [savingRoute, setSavingRoute] = useState(false);
  const [message, setMessage] = useState(null);

  const load = async () => {
    try {
      const res = await apiClient.get('/ai/providers');
      setStatus(res.data.providers || {});
    } catch (err) {
      setMessage({
        ok: false,
        text: err?.response?.data?.detail || 'Could not load provider keys.',
      });
    }
    try {
      const res = await apiClient.get('/ai/providers/routing');
      setRouting(res.data);
    } catch (err) {
      // Routing is optional — the key panel still works without it.
    }
  };

  useEffect(() => {
    load();
  }, []);

  const saveKey = async (id) => {
    const key = (drafts[id] || '').trim();
    if (!key) {
      setMessage({ ok: false, text: 'Paste a key first.' });
      return;
    }
    setBusy(id);
    setMessage(null);
    try {
      await apiClient.put(`/ai/providers/${id}/key`, { api_key: key });
      // Clear immediately: from the UI's perspective a key is write-only and is
      // never shown again after saving.
      setDrafts({ ...drafts, [id]: '' });
      await load();
      setMessage({ ok: true, text: `Saved ${id} key.` });
    } catch (err) {
      setMessage({
        ok: false,
        text: err?.response?.data?.detail || `Failed to save ${id} key.`,
      });
    } finally {
      setBusy(null);
    }
  };

  const deleteKey = async (id) => {
    if (!window.confirm(`Delete the stored ${id} key? Cloud requests using it will stop working.`)) {
      return;
    }
    setBusy(id);
    setMessage(null);
    try {
      await apiClient.delete(`/ai/providers/${id}/key`);
      await load();
      setMessage({ ok: true, text: `Deleted ${id} key.` });
    } catch (err) {
      setMessage({
        ok: false,
        text: err?.response?.data?.detail || `Failed to delete ${id} key.`,
      });
    } finally {
      setBusy(null);
    }
  };

  const saveRouting = async (task, provider) => {
    if (!routing) return;
    const next = { ...(routing.task_providers || {}), [task]: provider };
    setSavingRoute(true);
    setMessage(null);
    try {
      const res = await apiClient.put('/ai/providers/routing', { task_providers: next });
      setRouting(res.data);
      const label = (TASK_LABELS[task] || {}).label || task;
      setMessage({ ok: true, text: `${label} now uses ${provider || 'the default provider'}.` });
    } catch (err) {
      setMessage({
        ok: false,
        text: err?.response?.data?.detail || 'Failed to save routing.',
      });
    } finally {
      setSavingRoute(false);
    }
  };

  return (
    <div className="ai-provider-settings">
      <Card>
        <CardHeader title="Cloud AI providers (optional)" />
        <p className="ai-provider-intro">
          Local models stay the default. Add a key only if you want to use a cloud provider.
          Keys are stored on this machine at <code>~/.config/ecosystem/provider_keys.json</code>{' '}
          (owner-only) and are never shown again after saving.
        </p>

        {message && (
          <div className={`ai-provider-message ${message.ok ? 'is-ok' : 'is-error'}`} role="alert">
            {message.text}
          </div>
        )}

        <div className="ai-provider-list">
          {PROVIDERS.map(({ id, label, hint }) => {
            const st = status ? status[id] : null;
            const working = busy === id;
            return (
              <div className="ai-provider-row" key={id}>
                <div className="ai-provider-row-head">
                  <span className="ai-provider-name">{label}</span>
                  {st && st.configured ? (
                    <span className="ai-provider-badge is-configured">
                      configured ····{st.last4}
                    </span>
                  ) : (
                    <span className="ai-provider-badge">not configured</span>
                  )}
                </div>

                <div className="ai-provider-controls">
                  <TextField
                    type="password"
                    value={drafts[id] || ''}
                    onChange={(e) => setDrafts({ ...drafts, [id]: e.target.value })}
                    placeholder={st && st.configured ? 'Paste a new key to replace' : `API key from ${hint}`}
                    disabled={working}
                  />
                  <Button
                    onClick={() => saveKey(id)}
                    disabled={working || !(drafts[id] || '').trim()}
                  >
                    Save
                  </Button>
                  {st && st.configured && (
                    <Button variant="danger" onClick={() => deleteKey(id)} disabled={working}>
                      Delete
                    </Button>
                  )}
                </div>

                {st && st.configured && st.updated_at && (
                  <div className="ai-provider-updated">
                    updated {new Date(st.updated_at).toLocaleString()}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {routing && (
        <Card>
          <CardHeader title="Where each task runs" />
          <p className="ai-provider-intro">
            Cloud usage is metered. Send only what is worth paying for to a cloud provider and
            keep high-volume work local — for example cloud for security analysis, local for chat.
            Choosing a cloud provider here enables it automatically. This setting is shared across
            the whole ecosystem, not just OpenEye.
          </p>

          <div className="ai-provider-list">
            {(routing.tasks || []).map((task) => {
              const meta = TASK_LABELS[task] || { label: task, hint: '' };
              const value = (routing.task_providers || {})[task] || '';
              return (
                <div className="ai-provider-row ai-provider-route" key={task}>
                  <div>
                    <div className="ai-provider-name">{meta.label}</div>
                    {meta.hint && <div className="ai-provider-hint">{meta.hint}</div>}
                  </div>
                  <select
                    className="ai-provider-select"
                    value={value}
                    disabled={savingRoute}
                    onChange={(e) => saveRouting(task, e.target.value)}
                  >
                    <option value="">Default ({routing.default_provider})</option>
                    <option value="ollama">Local (Ollama)</option>
                    {PROVIDERS.map((p) => (
                      <option
                        key={p.id}
                        value={p.id}
                        disabled={!(status && status[p.id] && status[p.id].configured)}
                      >
                        {p.label}
                        {status && status[p.id] && status[p.id].configured ? '' : ' — add a key first'}
                      </option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}

export default AIProviderSettingsPage;
