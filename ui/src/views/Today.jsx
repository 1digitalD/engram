import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowRight, Calendar, Edit2, ExternalLink, Loader2 } from 'lucide-react';
import useStore from '../stores/useStore';
import { dailyAPI } from '../api/engram';
import { BucketBadge } from '../components/ui/Badge';
import styles from './Today.module.css';

function localDateISO(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export default function Today() {
  const { notes, tasks, upsertNote, updateNote, addToast } = useStore();
  const [dateStr] = useState(() => localDateISO());
  const [dailyId, setDailyId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [draftText, setDraftText] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const res = await dailyAPI.get(dateStr);
        const note = res.data;
        if (cancelled || !note?.id) return;
        upsertNote(note);
        setDailyId(note.id);
      } catch (e) {
        if (!cancelled) {
          setLoadError(e.message || 'Failed to load daily note');
          addToast({ type: 'error', message: e.message || 'Daily note failed' });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [dateStr, upsertNote, addToast]);

  const note = dailyId ? notes.find(n => n.id === dailyId) : null;

  useEffect(() => {
    if (!isEditing && note) setDraftText(note.raw_text || '');
  }, [note?.id, note?.raw_text, isEditing]);

  const dueToday = tasks.filter(
    t => t.due_date && t.due_date.slice(0, 10) === dateStr && t.status !== 'CANCELLED'
  );

  const startEditing = () => {
    setDraftText(note?.raw_text || '');
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setDraftText(note?.raw_text || '');
    setIsEditing(false);
  };

  const saveInline = async () => {
    if (!note || saving) return;
    setSaving(true);
    try {
      await updateNote(note.id, { raw_text: draftText });
      setIsEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      cancelEditing();
      return;
    }
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      saveInline();
    }
  };

  if (loading) {
    return (
      <div className={styles.page}>
        <p className={styles.loading}>
          <Loader2 size={16} className="spin" /> Loading today&rsquo;s note…
        </p>
      </div>
    );
  }

  if (loadError || !note) {
    return (
      <div className={styles.page}>
        <p className={styles.error}>{loadError || 'Daily note unavailable.'}</p>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerRow}>
          <div className={styles.titleBlock}>
            <Calendar size={18} className={styles.titleIcon} />
            <div>
              <h1>Today</h1>
              <p className={styles.sub}>
                {new Date(`${dateStr}T12:00:00`).toLocaleDateString('en-US', {
                  weekday: 'long',
                  month: 'long',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </p>
            </div>
          </div>
          <div className={styles.headerActions}>
            <BucketBadge bucket={note.bucket} />
            <Link to={`/notes/${note.id}`} className={styles.fullLink}>
              Full note <ExternalLink size={12} />
            </Link>
          </div>
        </div>
      </header>

      <div className={styles.grid}>
        <section className={styles.mainCol}>
          {!isEditing ? (
            <>
              <div className={styles.editBar}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={startEditing}>
                  <Edit2 size={13} /> Edit
                </button>
              </div>
              <article className={styles.body}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{note.raw_text}</ReactMarkdown>
              </article>
            </>
          ) : (
            <div className={styles.inlineEditor}>
              <textarea
                className={styles.textarea}
                value={draftText}
                onChange={e => setDraftText(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={18}
                autoFocus
              />
              <div className={styles.inlineActions}>
                <span className={styles.hint}>Cmd/Ctrl+Enter to save · Esc to cancel</span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={cancelEditing} disabled={saving}>
                  Cancel
                </button>
                <button type="button" className="btn btn-primary btn-sm" onClick={saveInline} disabled={saving}>
                  {saving ? <Loader2 size={13} className="spin" /> : null}
                  Save
                </button>
              </div>
            </div>
          )}
        </section>

        <aside className={styles.sideCol}>
          <h2 className={styles.sideTitle}>Due today</h2>
          {dueToday.length === 0 ? (
            <p className={styles.sideEmpty}>No tasks with this due date.</p>
          ) : (
            <ul className={styles.taskList}>
              {dueToday.map(t => (
                <li key={t.id}>
                  <Link to={`/tasks`} className={styles.taskLink}>
                    <ArrowRight size={12} />
                    <span className={t.status === 'DONE' ? styles.taskDone : ''}>{t.title}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </div>
  );
}
