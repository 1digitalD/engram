/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, X } from 'lucide-react';
import { v4API } from '../api/v4Client';
import MarkdownContent from '../components/MarkdownContent';
import styles from './V4EntityScreens.module.css';

const pluralTitle = {
  note: 'Notes',
  task: 'Tasks',
  project: 'Projects',
  area: 'Areas',
  person: 'People',
  resource: 'Resources',
};

function detailPath(entity) {
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function formatShortDate(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

const SORT_OPTIONS = [
  { value: 'updated_desc', label: 'Recently updated' },
  { value: 'created_desc', label: 'Recently created' },
  { value: 'due_asc', label: 'Due date (soonest)' },
  { value: 'title_asc', label: 'Title (A–Z)' },
  { value: 'status_asc', label: 'Status' },
];

function sortEntities(entities, sortBy) {
  const sorted = [...entities];
  const dateVal = (v) => (v ? new Date(v).getTime() : 0);
  switch (sortBy) {
    case 'created_desc':
      return sorted.sort((a, b) => dateVal(b.created_at) - dateVal(a.created_at));
    case 'due_asc':
      return sorted.sort((a, b) => {
        const av = a.due_at ? dateVal(a.due_at) : Infinity;
        const bv = b.due_at ? dateVal(b.due_at) : Infinity;
        return av - bv;
      });
    case 'title_asc':
      return sorted.sort((a, b) => (a.title || '').localeCompare(b.title || '', undefined, { sensitivity: 'base' }));
    case 'status_asc':
      return sorted.sort((a, b) => (a.status || '').localeCompare(b.status || '') || dateVal(b.updated_at) - dateVal(a.updated_at));
    case 'updated_desc':
    default:
      return sorted.sort((a, b) => dateVal(b.updated_at) - dateVal(a.updated_at));
  }
}

export default function V4EntityList({ type }) {
  const [entities, setEntities] = useState([]);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [sortBy, setSortBy] = useState('updated_desc');

  useEffect(() => {
    let active = true;
    v4API.entities.list({ type, limit: 100 })
      .then((response) => {
        if (active) setEntities(response.data || []);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [type]);

  async function handleCreate(event) {
    event.preventDefault();
    const trimmedTitle = title.trim();
    const trimmedContent = content.trim();
    if (type === 'note' ? !trimmedTitle && !trimmedContent : !trimmedTitle) return;
    setLoading(true);
    setError('');
    try {
      if (type === 'note') {
        const response = await v4API.capture({
          title: trimmedTitle || undefined,
          content: trimmedContent || trimmedTitle,
          source: 'ui',
          mode: 'auto',
        });
        setEntities((current) => [response.source_note, ...current]);
      } else {
        const response = await v4API.entities.create({
          type,
          title: trimmedTitle,
          content: trimmedContent || null,
        });
        setEntities((current) => [response.data, ...current]);
      }
      setTitle('');
      setContent('');
      setOpen(false);
    } catch (err) {
      setError(err.message || `Failed to create ${type}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.screen}>
      <section className={styles.listHeaderPanel}>
        <div className={styles.listHeading}>
          <h1>{pluralTitle[type]}</h1>
          <span className={styles.countPill}>{entities.length}</span>
          <div className={styles.listHeadingSpacer} />
          <label className={styles.sortControl}>
            <span className={styles.sortLabel}>Sort</span>
            <select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value)}
              aria-label={`Sort ${pluralTitle[type].toLowerCase()}`}
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className={`${styles.addButton} ${styles.addButtonIcon}`}
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={open ? `Close new ${type}` : `New ${type}`}
            title={open ? 'Close' : `New ${type}`}
          >
            {open
              ? <X size={14} strokeWidth={2.2} aria-hidden="true" />
              : <Plus size={14} strokeWidth={2.2} aria-hidden="true" />}
          </button>
        </div>
        {open && (
          <form onSubmit={handleCreate} className={styles.quickCreateForm} aria-label={`Create ${type}`}>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={type === 'note' ? 'Optional note title' : `New ${type} title`}
              aria-label="Title"
              autoFocus
            />
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder={type === 'note' ? 'Write the note. AI can safely extract metadata and links.' : 'Optional content'}
              aria-label="Content"
              rows={type === 'note' ? 2 : 1}
            />
            <button className={styles.primaryButton} type="submit" disabled={loading || (type === 'note' ? !title.trim() && !content.trim() : !title.trim())}>
              {loading ? 'Creating...' : `Create ${type}`}
            </button>
          </form>
        )}
        {error && <div className={styles.error}>{error}</div>}
      </section>

      <section className={styles.listPanel}>
        {entities.length === 0 ? (
          <p className={styles.emptyText}>No {pluralTitle[type].toLowerCase()} yet.</p>
        ) : (
          <ul className={styles.cards}>
            {sortEntities(entities, sortBy).map((entity) => {
              const created = formatShortDate(entity.created_at);
              const due = formatShortDate(entity.due_at);
              const isOverdue = entity.due_at && new Date(entity.due_at).getTime() < Date.now()
                && entity.status !== 'done' && entity.status !== 'completed' && entity.status !== 'cancelled';
              return (
                <li key={entity.id}>
                  <Link to={detailPath(entity)}>
                    <strong>{entity.title || 'Untitled'}</strong>
                    {entity.content && (
                      <MarkdownContent content={entity.content} compact />
                    )}
                    <span className={styles.metaRow}>
                      <span className={styles.statusPill}>{entity.status}</span>
                      {entity.properties?.priority && (
                        <span className={styles.priorityPill}>Priority {entity.properties.priority}</span>
                      )}
                      {due && (
                        <span className={`${styles.mutedMeta} ${isOverdue ? styles.dueOverdue : ''}`} title={`Due ${due}`}>
                          Due {due}
                        </span>
                      )}
                      {created && (
                        <span className={styles.mutedMeta} title={`Created ${created}`}>
                          Created {created}
                        </span>
                      )}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
