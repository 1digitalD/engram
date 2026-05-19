import React, { useEffect, useState } from 'react';
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
    loadSuggestions()
      .catch((err) => setError(err.message || 'Failed to load suggestions'))
      .finally(() => setLoading(false));
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
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Engram v4 Review</p>
        <h1>Approve the risky changes.</h1>
        <p>AI can propose creation and linking work here; entity creation remains review-gated.</p>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <h2>Pending suggestions</h2>
          <button type="button" onClick={() => loadSuggestions()} disabled={loading || !!busyId}>
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
                    onClick={() => resolveSuggestion(suggestion.id, 'accept')}
                    disabled={!!busyId}
                  >
                    {busyId === suggestion.id ? 'Working...' : 'Accept'}
                  </button>
                  <button
                    type="button"
                    className={styles.secondary}
                    onClick={() => resolveSuggestion(suggestion.id, 'dismiss')}
                    disabled={!!busyId}
                  >
                    Dismiss
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
