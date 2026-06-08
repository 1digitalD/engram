/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { X } from 'lucide-react';
import { v4API } from '../api/v4Client';
import CardActions from '../components/CardActions';
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

function formatIntent(intent) {
  if (!intent) return '';
  return String(intent).replace(/_/g, ' ');
}

function NoteCard({ note, onChanged, fromState, showPreview = true }) {
  const ts = note.created_at || note.updated_at;
  const pending = note.pending_suggestion_count || 0;
  const aiPending = note.ai?.status === 'pending';
  const aiError = note.ai?.status === 'failed';
  const intent = formatIntent(note.ai?.intent);
  const tagList = note.tags || [];
  return (
    <li className={`${styles.noteCard} cardActionsParent`}>
      <CardActions entity={note} onChanged={onChanged} />
      <div className={styles.noteSurface}>
        <Link to={notePath(note)} state={fromState} className={styles.noteLink}>
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
          {showPreview && note.content && (
            <MarkdownContent content={note.content} compact />
          )}
        </Link>
        <div className={styles.noteMetaRow}>
          <div className={styles.noteBadges}>
            {aiPending && <span className={`${styles.badge} ${styles.badge_warn}`}>AI pending</span>}
            {aiError && <span className={`${styles.badge} ${styles.badge_error}`}>AI error</span>}
            {intent && <span className={styles.badge}>Intent · {intent}</span>}
            {pending > 0 && (
              <span className={`${styles.badge} ${styles.badge_accent}`}>{pending} suggestion{pending === 1 ? '' : 's'}</span>
            )}
          </div>
          {tagList.length > 0 && (
            <div className={styles.noteTags} aria-label="Note tags">
              {tagList.slice(0, 4).map((tag) => (
                <Link
                  key={tag.id || tag.name}
                  to={`/search?tag=${encodeURIComponent(tag.name)}`}
                  className={styles.tagChip}
                >
                  #{tag.name}
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

export default function V4Inbox() {
  const location = useLocation();
  const fromState = { from: location.pathname + location.search };
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

  useEffect(() => { loadInbox(); }, []);

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
        <header className={styles.captureHeader}>
          <div className={styles.captureHeaderCopy}>
            <p className={styles.eyebrow}>Capture inbox</p>
            <h1>Capture first, then review or file the note.</h1>
            <p>
              Raw notes land here. Review extraction outcomes below or move into the full notes library when you just need retrieval.
            </p>
          </div>
          <div className={styles.captureHeaderActions}>
            <Link to="/suggestions" className={styles.captureHeaderLink}>Review suggestions</Link>
            <Link to="/notes" className={styles.captureHeaderLink}>All notes</Link>
          </div>
        </header>
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
            <Link to="/suggestions" className={styles.sectionLink}>Open review queue</Link>
          </header>
          <ul className={styles.noteList}>
            {needsReview.map((n) => (
              <NoteCard key={n.id} note={n} fromState={fromState} onChanged={loadInbox} />
            ))}
          </ul>
        </section>
      )}

      <section className={styles.recentPanel}>
        <header className={styles.sectionHeader}>
          <h2>Captured recently</h2>
          <span className={styles.sectionHint}>Recent source notes, without the review queue mixed in.</span>
          <span className={styles.countPill}>{recent.length}</span>
          <Link to="/notes" className={styles.sectionLink}>Open notes</Link>
        </header>
        {recent.length === 0 ? (
          <p className={styles.empty}>No notes yet.</p>
        ) : (
          <>
            <ul className={styles.noteList}>
              {recent.slice(0, 10).map((n) => (
                <NoteCard key={n.id} note={n} fromState={fromState} onChanged={loadInbox} showPreview={false} />
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
