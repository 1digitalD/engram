import React from 'react';
import { useEffect, useState } from 'react';
import { v4API } from '../api/v4Client';
import styles from './V4Inbox.module.css';

function entityTitle(entity) {
  return entity?.title || entity?.content?.slice(0, 80) || 'Untitled note';
}

function suggestionLabel(suggestion) {
  const payload = suggestion?.payload || {};
  return payload.title || suggestion?.suggestion_type || 'Suggestion';
}

export default function V4Inbox() {
  const [content, setContent] = useState('');
  const [notes, setNotes] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function loadRecentNotes() {
    const response = await v4API.entities.list({ type: 'note', limit: 20 });
    setNotes(response.data || []);
  }

  useEffect(() => {
    loadRecentNotes().catch((err) => setError(err.message));
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = content.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setError('');
    try {
      const captureResult = await v4API.capture({
        content: trimmed,
        source: 'ui',
        mode: 'auto',
      });
      setResult(captureResult);
      setContent('');
      if (captureResult.source_note) {
        setNotes((current) => [
          captureResult.source_note,
          ...current.filter((note) => note.id !== captureResult.source_note.id),
        ]);
      }
    } catch (err) {
      setError(err.message || 'Capture failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.inbox}>
      <section className={styles.capturePanel}>
        <p className={styles.eyebrow}>Engram v4 Inbox</p>
        <h1>Capture first. Sort later.</h1>
        <form onSubmit={handleSubmit} className={styles.form}>
          <label htmlFor="capture-content">Capture text</label>
          <textarea
            id="capture-content"
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Paste a note, reminder, task idea, person mention, or project update..."
            rows={7}
          />
          <button type="submit" disabled={!content.trim() || loading}>
            {loading ? 'Capturing...' : 'Capture'}
          </button>
        </form>
        {error && <div className={styles.error}>{error}</div>}
      </section>

      {result && (
        <section className={styles.resultPanel} aria-label="Capture result">
          <h2>Saved source note</h2>
          <article className={styles.noteCard}>
            <strong>{entityTitle(result.source_note)}</strong>
            <p>{result.source_note?.content}</p>
          </article>

          {!!result.warnings?.length && (
            <div className={styles.warning}>
              <h3>AI warning</h3>
              {result.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          )}

          {!!result.applied_changes?.length && (
            <div>
              <h3>Applied safely</h3>
              <ul className={styles.list}>
                {result.applied_changes.map((change, index) => (
                  <li key={`${change.type}-${index}`}>{change.type}</li>
                ))}
              </ul>
            </div>
          )}

          {!!result.suggestions?.length && (
            <div>
              <h3>Suggestions for review</h3>
              <ul className={styles.list}>
                {result.suggestions.map((suggestion) => (
                  <li key={suggestion.id || suggestionLabel(suggestion)}>{suggestionLabel(suggestion)}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      <section className={styles.recentPanel}>
        <h2>Recent notes</h2>
        {notes.length === 0 ? (
          <p>No notes captured yet.</p>
        ) : (
          <ul className={styles.noteList}>
            {notes.map((note) => (
              <li key={note.id}>
                <strong>{entityTitle(note)}</strong>
                <span>{note.content}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
