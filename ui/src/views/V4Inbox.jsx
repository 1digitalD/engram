/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';
import { v4API } from '../api/v4Client';
import MarkdownContent from '../components/MarkdownContent';
import MarkdownEditor from '../components/MarkdownEditor';
import styles from './V4Inbox.module.css';

function entityTitle(entity) {
  return entity?.title || entity?.content?.slice(0, 80) || 'Untitled note';
}

function notePath(entity) {
  return `/notes/${entity.id}`;
}

function formatTimestamp(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const diffMs = now - date;
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  const sameYear = date.getFullYear() === now.getFullYear();
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' }),
  });
}

function NoteCard({ note }) {
  const ts = note.created_at || note.updated_at;
  const pending = note.pending_suggestion_count || 0;
  const aiPending = note.ai?.status === 'pending';
  const aiError = note.ai?.status === 'failed';
  const tagList = note.tags || [];
  return (
    <li className={styles.noteCard}>
      <Link to={notePath(note)} className={styles.noteLink}>
        <div className={styles.noteHeader}>
          <strong>{entityTitle(note)}</strong>
          {ts && (
            <time
              className={styles.noteTimestamp}
              dateTime={ts}
              title={new Date(ts).toLocaleString()}
            >
              {formatTimestamp(ts)}
            </time>
          )}
        </div>
        {note.content && (
          <MarkdownContent content={note.content} compact />
        )}
        <div className={styles.noteBadges}>
          {aiPending && <span className={`${styles.badge} ${styles.badge_warn}`}>AI pending</span>}
          {aiError && <span className={`${styles.badge} ${styles.badge_error}`}>AI error</span>}
          {pending > 0 && (
            <span className={`${styles.badge} ${styles.badge_accent}`}>{pending} suggestion{pending === 1 ? '' : 's'}</span>
          )}
          {tagList.slice(0, 4).map((tag) => (
            <Link
              key={tag.id || tag.name}
              to={`/search?tag=${encodeURIComponent(tag.name)}`}
              className={styles.tagChip}
              onClick={(e) => e.stopPropagation()}
            >
              #{tag.name}
            </Link>
          ))}
        </div>
      </Link>
    </li>
  );
}

export default function V4Inbox() {
  const [content, setContent] = useState('');
  const [needsReview, setNeedsReview] = useState([]);
  const [recent, setRecent] = useState([]);
  const [captureLog, setCaptureLog] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function loadInbox() {
    try {
      const data = await v4API.inbox({ limit: 30 });
      setNeedsReview(data.needs_review || []);
      setRecent(data.recent || []);
    } catch (err) {
      setError(err.message || 'Failed to load inbox');
    }
  }

  useEffect(() => { loadInbox(); /* eslint-disable-next-line */ }, []);

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
      setContent('');
      setCaptureLog((prev) => [{ id: captureResult.source_note?.id || Date.now(), ...captureResult }, ...prev].slice(0, 5));
      await loadInbox();
    } catch (err) {
      setError(err.message || 'Capture failed');
    } finally {
      setLoading(false);
    }
  }

  function dismissCaptureResult(id) {
    setCaptureLog((prev) => prev.filter((r) => r.id !== id));
  }

  return (
    <main className={styles.inbox}>
      <section className={styles.capturePanel}>
        <form onSubmit={handleSubmit} className={styles.form}>
          <MarkdownEditor
            value={content}
            onChange={setContent}
            placeholder="Paste a note, reminder, task idea, person mention, or project update…"
            minRows={6}
            autoFocus
          />
          <button type="submit" className={styles.captureButton} disabled={!content.trim() || loading}>
            {loading ? 'Capturing...' : 'Capture'}
          </button>
        </form>
        {error && <div className={styles.error}>{error}</div>}

        {captureLog.length > 0 && (
          <ul className={styles.captureLog} aria-label="Recent captures">
            {captureLog.map((r) => {
              const applied = (r.applied_changes || []).length;
              const suggested = (r.suggestions || []).length;
              return (
                <li key={r.id} className={styles.captureLogItem}>
                  <div className={styles.captureLogBody}>
                    <strong>Saved · {entityTitle(r.source_note)}</strong>
                    <span className={styles.captureLogMeta}>
                      {applied > 0 && <span>{applied} applied</span>}
                      {suggested > 0 && (
                        <Link to="/suggestions">{suggested} suggestion{suggested === 1 ? '' : 's'} pending</Link>
                      )}
                      {(r.warnings || []).map((w) => (
                        <span key={w} className={styles.warning}>{w}</span>
                      ))}
                    </span>
                  </div>
                  <button
                    type="button"
                    className={styles.dismiss}
                    onClick={() => dismissCaptureResult(r.id)}
                    aria-label="Dismiss"
                    title="Dismiss"
                  >
                    <X size={12} strokeWidth={2.4} aria-hidden="true" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {needsReview.length > 0 && (
        <section className={`${styles.recentPanel} ${styles.recentPanel_review}`}>
          <header className={styles.sectionHeader}>
            <h2>Needs review</h2>
            <span className={styles.sectionHint}>Pending suggestions or AI errors</span>
            <span className={styles.countPill}>{needsReview.length}</span>
          </header>
          <ul className={styles.noteList}>
            {needsReview.map((n) => (
              <NoteCard key={n.id} note={n} />
            ))}
          </ul>
        </section>
      )}

      <section className={styles.recentPanel}>
        <header className={styles.sectionHeader}>
          <h2>Captured recently</h2>
          <span className={styles.countPill}>{recent.length}</span>
        </header>
        {recent.length === 0 ? (
          <p className={styles.empty}>No notes yet.</p>
        ) : (
          <>
            <ul className={styles.noteList}>
              {recent.slice(0, 10).map((n) => (
                <NoteCard key={n.id} note={n} />
              ))}
            </ul>
            {recent.length > 10 && (
              <Link to="/notes" className={styles.showAllLink}>
                Show all {recent.length} notes →
              </Link>
            )}
          </>
        )}
      </section>
    </main>
  );
}
