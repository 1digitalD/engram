/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import MarkdownContent from '../components/MarkdownContent';
import mdStyles from '../components/MarkdownContent.module.css';
import styles from './V4Inbox.module.css';

function entityTitle(entity) {
  return entity?.title || entity?.content?.slice(0, 80) || 'Untitled note';
}

function notePath(entity) {
  return `/notes/${entity.id}`;
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

  useEffect(() => {
    let active = true;
    v4API.entities.list({ type: 'note', limit: 20 })
      .then((response) => {
        if (active) setNotes(response.data || []);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
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
        <form onSubmit={handleSubmit} className={styles.form}>
          <label htmlFor="capture-content" className={styles.srOnly}>Capture text</label>
          <textarea
            id="capture-content"
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Paste a note, reminder, task idea, person mention, or project update..."
            rows={6}
          />
          <button type="submit" disabled={!content.trim() || loading}>
            {loading ? 'Capturing...' : 'Capture'}
          </button>
        </form>
        {error && <div className={styles.error}>{error}</div>}

        {result && (
          <div className={styles.resultPanel} aria-label="Capture result">
            <p className={styles.resultHead}>Saved</p>
            <strong>{entityTitle(result.source_note)}</strong>

            {!!result.warnings?.length && (
              <div className={styles.warning}>
                {result.warnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
              </div>
            )}

            {!!result.applied_changes?.length && (
              <p className={styles.resultMeta}>
                Applied: {result.applied_changes.map((c) => c.type).join(', ')}
              </p>
            )}

            {!!result.suggestions?.length && (
              <p className={styles.resultMeta}>
                {result.suggestions.length} suggestion{result.suggestions.length !== 1 ? 's' : ''} pending &rarr;{' '}
                <Link to="/suggestions">Review</Link>
              </p>
            )}
          </div>
        )}
      </section>

      <section className={styles.recentPanel}>
        <h2>Recent notes</h2>
        {notes.length === 0 ? (
          <p className={styles.empty}>No notes captured yet.</p>
        ) : (
          <ul className={styles.noteList}>
            {notes.map((note) => (
              <li key={note.id}>
                <Link to={notePath(note)} className={styles.noteLink}>
                  <strong>{entityTitle(note)}</strong>
                  {note.content && (
                    <div className={`${mdStyles.md} ${mdStyles.mdCompact}`}>
                      <MarkdownContent content={note.content} />
                    </div>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
