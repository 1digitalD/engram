/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Check, Pencil, RefreshCw, RotateCcw, X } from 'lucide-react';
import { v4API } from '../api/v4Client';
import styles from './V4Suggestions.module.css';

const ENTITY_TYPES = ['task', 'project', 'area', 'resource', 'person'];

function suggestionTitle(suggestion) {
  const payload = suggestion?.payload || {};
  return payload.title || suggestion?.suggestion_type || 'Suggestion';
}

function suggestionDetail(suggestion) {
  const payload = suggestion?.payload || {};
  if (suggestion.operation_type === 'link_existing') {
    return `Link to ${payload.target_type || 'entity'} · ${payload.relationship_type || 'related'}`;
  }
  return `${payload.type || suggestion.operation_type} · ${payload.status || 'review required'}`;
}

function SuggestionCard({ suggestion, onAccept, onDismiss, onUpdate, onReprocess, busy }) {
  const isCreate = suggestion.operation_type === 'create_entity';
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({
    title: suggestion.payload?.title || '',
    content: suggestion.payload?.content || '',
    type: suggestion.payload?.type || '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSave() {
    setSaving(true);
    setError('');
    try {
      await onUpdate(suggestion.id, draft);
      setEditing(false);
    } catch (err) {
      setError(err.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setDraft({
      title: suggestion.payload?.title || '',
      content: suggestion.payload?.content || '',
      type: suggestion.payload?.type || '',
    });
    setEditing(false);
    setError('');
  }

  return (
    <li className={`${styles.card} ${editing ? styles.cardEditing : ''}`}>
      {editing ? (
        <div className={styles.editForm}>
          <div className={styles.editRow}>
            <input
              className={styles.editInput}
              value={draft.title}
              onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
              placeholder="Title"
              aria-label="Title"
              autoFocus
            />
            <select
              className={styles.editSelect}
              value={draft.type}
              onChange={(e) => setDraft((d) => ({ ...d, type: e.target.value }))}
              aria-label="Entity type"
            >
              {ENTITY_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <textarea
            className={styles.editTextarea}
            value={draft.content}
            onChange={(e) => setDraft((d) => ({ ...d, content: e.target.value }))}
            placeholder="Description"
            aria-label="Description"
            rows={3}
          />
          {error && <p className={styles.editError}>{error}</p>}
          <div className={styles.editActions}>
            <button
              type="button"
              className={styles.saveButton}
              onClick={handleSave}
              disabled={saving || !draft.title.trim()}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              className={styles.cancelButton}
              onClick={handleCancel}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className={styles.cardBody}>
            <strong>{suggestionTitle(suggestion)}</strong>
            <span>{suggestionDetail(suggestion)}</span>
            {suggestion.source_note_title && (
              <span className={styles.sourceNote}>from · {suggestion.source_note_title}</span>
            )}
            {suggestion.reason && <p>{suggestion.reason}</p>}
          </div>
          <div className={styles.actions}>
            {isCreate && (
              <button
                type="button"
                className={`${styles.iconButton} ${styles.editButton}`}
                onClick={() => setEditing(true)}
                disabled={busy}
                aria-label="Edit"
                title="Edit"
              >
                <Pencil size={14} strokeWidth={2.2} aria-hidden="true" />
              </button>
            )}
            {suggestion.source_entity_id && (
              <button
                type="button"
                className={`${styles.iconButton} ${styles.reprocessButton}`}
                onClick={() => onReprocess(suggestion.source_entity_id)}
                disabled={busy}
                aria-label="Re-run AI"
                title="Re-run AI extraction"
              >
                <RotateCcw size={14} strokeWidth={2.2} aria-hidden="true" />
              </button>
            )}
            <button
              type="button"
              className={`${styles.iconButton} ${styles.acceptButton}`}
              onClick={() => onAccept(suggestion.id)}
              disabled={busy}
              aria-label="Accept"
              title="Accept"
            >
              <Check size={16} strokeWidth={2.4} aria-hidden="true" />
            </button>
            <button
              type="button"
              className={`${styles.iconButton} ${styles.dismissButton}`}
              onClick={() => onDismiss(suggestion.id)}
              disabled={busy}
              aria-label="Dismiss"
              title="Dismiss"
            >
              <X size={16} strokeWidth={2.4} aria-hidden="true" />
            </button>
          </div>
        </>
      )}
    </li>
  );
}

export default function V4Suggestions() {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');

  async function loadSuggestions() {
    setError('');
    setLoading(true);
    try {
      const response = await v4API.suggestions.list({ status: 'pending' });
      setSuggestions(response.data || []);
    } catch (err) {
      setError(err.message || 'Failed to load suggestions');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSuggestions();
  }, []);

  async function handleAccept(id) {
    if (busyId) return;
    setBusyId(id);
    setError('');
    try {
      await v4API.suggestions.accept(id);
      setSuggestions((current) => current.filter((s) => s.id !== id));
    } catch (err) {
      setError(err.message || 'Failed to accept suggestion');
    } finally {
      setBusyId('');
    }
  }

  async function handleDismiss(id) {
    if (busyId) return;
    setBusyId(id);
    setError('');
    try {
      await v4API.suggestions.dismiss(id);
      setSuggestions((current) => current.filter((s) => s.id !== id));
    } catch (err) {
      setError(err.message || 'Failed to dismiss suggestion');
    } finally {
      setBusyId('');
    }
  }

  async function handleUpdate(id, data) {
    const response = await v4API.suggestions.update(id, data);
    setSuggestions((current) =>
      current.map((s) => (s.id === id ? { ...s, payload: response.data.payload } : s))
    );
  }

  async function handleReprocess(entityId) {
    if (busyId) return;
    setBusyId(`reprocess-${entityId}`);
    setError('');
    try {
      await v4API.reprocess(entityId);
      await loadSuggestions();
    } catch (err) {
      setError(err.message || 'Failed to reprocess note');
      setLoading(false);
    } finally {
      setBusyId('');
    }
  }

  return (
    <main className={styles.suggestions}>
      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <h2>Suggestions{suggestions.length ? ` · ${suggestions.length}` : ''}</h2>
          <button
            type="button"
            className={styles.refreshButton}
            onClick={loadSuggestions}
            disabled={loading || !!busyId}
            aria-label="Refresh suggestions"
            title="Refresh"
          >
            <RefreshCw size={12} strokeWidth={2.2} aria-hidden="true" />
            Refresh
          </button>
        </div>
        {error && <div className={styles.error}>{error}</div>}
        {loading ? (
          <p>Loading suggestions...</p>
        ) : suggestions.length === 0 ? (
          <p>No pending suggestions.</p>
        ) : (
          <ul className={styles.list}>
            {suggestions.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                onAccept={handleAccept}
                onDismiss={handleDismiss}
                onUpdate={handleUpdate}
                onReprocess={handleReprocess}
                busy={!!busyId}
              />
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
