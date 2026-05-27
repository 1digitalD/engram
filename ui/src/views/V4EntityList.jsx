/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowDown, ArrowUp, Plus, X } from 'lucide-react';
import { v4API } from '../api/v4Client';
import CardActions from '../components/CardActions';
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

const STATUS_BY_TYPE = {
  note: ['active', 'processed', 'archived'],
  task: ['open', 'in_progress', 'waiting', 'blocked', 'done', 'cancelled'],
  project: ['active', 'on_hold', 'completed', 'cancelled'],
  area: ['active', 'archived'],
  person: ['active', 'archived'],
  resource: ['active', 'archived'],
};

const PRIORITY_OPTIONS = ['urgent', 'high', 'medium', 'low'];

const SORT_FIELDS = [
  { value: 'updated', label: 'Updated', getter: (e) => e.updated_at, type: 'date', defaultDir: 'desc' },
  { value: 'created', label: 'Created', getter: (e) => e.created_at, type: 'date', defaultDir: 'desc' },
  { value: 'due', label: 'Due', getter: (e) => e.due_at, type: 'date', defaultDir: 'asc' },
  { value: 'title', label: 'Title', getter: (e) => e.title || '', type: 'text', defaultDir: 'asc' },
  { value: 'status', label: 'Status', getter: (e) => e.status || '', type: 'text', defaultDir: 'asc' },
];

const SESSION_KEY = (type) => `v4_entity_list_${type}`;

function loadPersistedState(type) {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY(type));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Validate it matches known shape to avoid stale/invalid state
    if (!parsed || typeof parsed.sortField !== 'string') return null;
    return parsed;
  } catch {
    return null;
  }
}

function persistState(type, state) {
  try {
    sessionStorage.setItem(SESSION_KEY(type), JSON.stringify(state));
  } catch {
    // Storage unavailable — ignore.
  }
}

function parseLifetime(value) {
  if (value === 'active' || value === 'archived' || value === 'all') return value;
  return 'active';
}


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

function sortEntities(entities, sortField, sortDir) {
  const field = SORT_FIELDS.find((f) => f.value === sortField) || SORT_FIELDS[0];
  const sign = sortDir === 'asc' ? 1 : -1;
  const dateVal = (v) => (v ? new Date(v).getTime() : null);
  const sorted = [...entities];

  if (field.type === 'date') {
    // Null dates sort to the bottom regardless of direction.
    sorted.sort((a, b) => {
      const av = dateVal(field.getter(a));
      const bv = dateVal(field.getter(b));
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return (av - bv) * sign;
    });
  } else {
    sorted.sort((a, b) => {
      const av = String(field.getter(a) || '');
      const bv = String(field.getter(b) || '');
      return av.localeCompare(bv, undefined, { sensitivity: 'base' }) * sign;
    });
  }
  return sorted;
}

export default function V4EntityList({ type }) {
  const location = useLocation();
  const fromState = { from: location.pathname + location.search };
  const [entities, setEntities] = useState([]);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const _init = loadListState(type);
  const [sortField, setSortField] = useState(_init?.sortField ?? 'updated');
  const [sortDir, setSortDir] = useState(_init?.sortDir ?? 'desc');
  const [statusFilter, setStatusFilter] = useState(_init?.statusFilter ?? '');
  const [priorityFilter, setPriorityFilter] = useState(_init?.priorityFilter ?? '');
  const [lifecycleFilter, setLifecycleFilter] = useState(parseLifetime(_init?.lifecycleFilter));

  useEffect(() => {
    let active = true;
    const params = { type, limit: 100 };
    if (lifecycleFilter && lifecycleFilter !== 'all') params.lifecycle = lifecycleFilter;
    v4API.entities.list(params)
      .then((response) => {
        if (active) setEntities(response.data || []);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [type, lifecycleFilter]);

  // Persist sort/filter state on every change.
  useEffect(() => {
    persistListState(type, { sortField, sortDir, statusFilter, priorityFilter, lifecycleFilter });
  }, [type, sortField, sortDir, statusFilter, priorityFilter, lifecycleFilter]);

  const statusOptions = STATUS_BY_TYPE[type] || [];

  const visibleEntities = useMemo(() => {
    let list = entities;
    if (statusFilter) list = list.filter((e) => e.status === statusFilter);
    if (priorityFilter) {
      list = list.filter((e) => {
        const p = e.properties?.priority || '';
        return priorityFilter === '__none__' ? !p : p === priorityFilter;
      });
    }
    return sortEntities(list, sortField, sortDir);
  }, [entities, statusFilter, priorityFilter, sortField, sortDir]);

  function toggleSortDir() {
    setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
  }

  function onSortFieldChange(value) {
    const next = SORT_FIELDS.find((f) => f.value === value);
    setSortField(value);
    if (next) setSortDir(next.defaultDir);
  }

  const activeFilterCount = [statusFilter, priorityFilter, lifecycleFilter !== 'active' ? '1' : ''].filter(Boolean).length;

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
          <span className={styles.countPill}>{visibleEntities.length}{activeFilterCount > 0 && entities.length !== visibleEntities.length ? ` / ${entities.length}` : ''}</span>
          <div className={styles.listHeadingSpacer} />
          <div className={styles.listToolbar}>
            <label className={styles.filterControl}>
              <span className={styles.sortLabel}>Status</span>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                aria-label={`Filter ${pluralTitle[type].toLowerCase()} by status`}
              >
                <option value="">all</option>
                {statusOptions.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </label>
            {type === 'task' && (
              <label className={styles.filterControl}>
                <span className={styles.sortLabel}>Priority</span>
                <select
                  value={priorityFilter}
                  onChange={(event) => setPriorityFilter(event.target.value)}
                  aria-label="Filter tasks by priority"
                >
                  <option value="">all</option>
                  {PRIORITY_OPTIONS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                  <option value="__none__">no priority</option>
                </select>
              </label>
            )}
            <label className={styles.filterControl}>
              <span className={styles.sortLabel}>Lifecycle</span>
              <select
                value={lifecycleFilter}
                onChange={(event) => setLifecycleFilter(event.target.value)}
                aria-label={`Lifecycle filter for ${pluralTitle[type].toLowerCase()}`}
              >
                <option value="active">active</option>
                <option value="archived">archived</option>
                <option value="all">all</option>
              </select>
            </label>
            <label className={styles.sortControl}>
              <span className={styles.sortLabel}>Sort</span>
              <select
                value={sortField}
                onChange={(event) => onSortFieldChange(event.target.value)}
                aria-label={`Sort ${pluralTitle[type].toLowerCase()}`}
              >
                {SORT_FIELDS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <button
                type="button"
                className={styles.sortDirButton}
                onClick={toggleSortDir}
                aria-label={`Sort direction: ${sortDir === 'asc' ? 'ascending' : 'descending'} (click to flip)`}
                title={sortDir === 'asc' ? 'Ascending — click to descend' : 'Descending — click to ascend'}
              >
                {sortDir === 'asc'
                  ? <ArrowUp size={13} strokeWidth={2.4} aria-hidden="true" />
                  : <ArrowDown size={13} strokeWidth={2.4} aria-hidden="true" />}
              </button>
            </label>
          </div>
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
        {visibleEntities.length === 0 ? (
          <p className={styles.emptyText}>
            {entities.length === 0
              ? `No ${pluralTitle[type].toLowerCase()} yet.`
              : `No ${pluralTitle[type].toLowerCase()} match the current filters.`}
          </p>
        ) : (
          <ul className={styles.cards}>
            {visibleEntities.map((entity) => {
              const created = formatShortDate(entity.created_at);
              const due = formatShortDate(entity.due_at);
              const isOverdue = entity.due_at && new Date(entity.due_at).getTime() < Date.now()
                && entity.status !== 'done' && entity.status !== 'completed' && entity.status !== 'cancelled';
              return (
                <li key={entity.id} className="cardActionsParent">
                  <CardActions
                    entity={entity}
                    onChanged={() => setEntities((cur) => cur.filter((e) => e.id !== entity.id))}
                  />
                  <Link to={detailPath(entity)} state={fromState}>
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
                  {(entity.tags || []).length > 0 && (
                    <span className={styles.cardTagRow}>
                      {entity.tags.map((tag) => (
                        <Link
                          key={tag.id || tag.name}
                          to={`/search?tag=${encodeURIComponent(tag.name)}`}
                          className={styles.cardTagChip}
                          title={`Find all items tagged #${tag.name}`}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {tag.name}
                        </Link>
                      ))}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
