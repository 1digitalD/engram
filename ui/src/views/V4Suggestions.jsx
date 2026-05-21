/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Check, RefreshCw, X } from 'lucide-react';
import { v4API } from '../api/v4Client';
import styles from './V4Suggestions.module.css';

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

export default function V4Suggestions() {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');

  async function loadSuggestions() {
    setError('');
    const response = await v4API.suggestions.list({ status: 'pending' });
    setSuggestions(response.data || []);
  }

  useEffect(() => {
    let active = true;
    v4API.suggestions.list({ status: 'pending' })
      .then((response) => {
        if (active) setSuggestions(response.data || []);
      })
      .catch((err) => {
        if (active) setError(err.message || 'Failed to load suggestions');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function resolveSuggestion(id, action) {
    if (busyId) return;
    setBusyId(id);
    setError('');
    try {
      if (action === 'accept') {
        await v4API.suggestions.accept(id);
      } else {
        await v4API.suggestions.dismiss(id);
      }
      setSuggestions((current) => current.filter((suggestion) => suggestion.id !== id));
    } catch (err) {
      setError(err.message || `Failed to ${action} suggestion`);
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
            onClick={() => loadSuggestions()}
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
              <li key={suggestion.id} className={styles.card}>
                <div>
                  <strong>{suggestionTitle(suggestion)}</strong>
                  <span>{suggestionDetail(suggestion)}</span>
                  {suggestion.reason && <p>{suggestion.reason}</p>}
                </div>
                <div className={styles.actions}>
                  <button
                    type="button"
                    className={`${styles.iconButton} ${styles.acceptButton}`}
                    onClick={() => resolveSuggestion(suggestion.id, 'accept')}
                    disabled={!!busyId}
                    aria-label="Accept"
                    title="Accept"
                  >
                    <Check size={16} strokeWidth={2.4} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className={`${styles.iconButton} ${styles.dismissButton}`}
                    onClick={() => resolveSuggestion(suggestion.id, 'dismiss')}
                    disabled={!!busyId}
                    aria-label="Dismiss"
                    title="Dismiss"
                  >
                    <X size={16} strokeWidth={2.4} aria-hidden="true" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
