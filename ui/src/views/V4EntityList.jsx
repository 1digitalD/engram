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
const SIMPLE_ARCHIVE_TYPES = new Set(['note', 'area', 'person', 'resource']);
const TASK_GROUP_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'status', label: 'Status' },
  { value: 'priority', label: 'Priority' },
  { value: 'due', label: 'Due' },
  { value: 'project', label: 'Project' },
  { value: 'area', label: 'Area' },
  { value: 'person', label: 'Assignee' },
];

const SORT_FIELDS = [
  { value: 'updated', label: 'Updated', getter: (e) => e.updated_at, type: 'date', defaultDir: 'desc' },
  { value: 'created', label: 'Created', getter: (e) => e.created_at, type: 'date', defaultDir: 'desc' },
  { value: 'due', label: 'Due', getter: (e) => e.due_at, type: 'date', defaultDir: 'asc' },
  { value: 'title', label: 'Title', getter: (e) => e.title || '', type: 'text', defaultDir: 'asc' },
  { value: 'status', label: 'Status', getter: (e) => e.status || '', type: 'text', defaultDir: 'asc' },
];

const SESSION_KEY = (() => {
  // Scope storage to this tab so multiple tabs don't interfere with each other.
  const tabId = Math.random().toString(36).slice(2);
  return (type) => `v4_list_${type}_${tabId}`;
})();

function loadListState(type) {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY(type));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.sortField !== 'string') return null;
    return parsed;
  } catch {
    return null;
  }
}

function persistListState(type, state) {
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

function parseStatusFilter(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return [value];
}

function formatFilterLabel(value) {
  if (!value) return '';
  return value.replaceAll('_', ' ');
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

function linkedCountLabel(value, singular, plural = `${singular}s`) {
  return `${value} ${value === 1 ? singular : plural}`;
}

function startOfDay(value) {
  const d = new Date(value);
  d.setHours(0, 0, 0, 0);
  return d;
}

function taskGroupDescriptors(entity, groupBy, now = new Date()) {
  if (groupBy === 'status') {
    return [{ key: `status:${entity.status || 'unknown'}`, label: formatFilterLabel(entity.status || 'unknown'), order: STATUS_BY_TYPE.task.indexOf(entity.status) }];
  }
  if (groupBy === 'priority') {
    const priority = entity.properties?.priority || '';
    return [{
      key: `priority:${priority || 'none'}`,
      label: priority ? `Priority ${priority}` : 'No priority',
      order: priority ? PRIORITY_OPTIONS.indexOf(priority) : PRIORITY_OPTIONS.length,
    }];
  }
  if (groupBy === 'due') {
    if (!entity.due_at) return [{ key: 'due:none', label: 'No due date', order: 4 }];
    const due = new Date(entity.due_at);
    if (Number.isNaN(due.getTime())) return [{ key: 'due:none', label: 'No due date', order: 4 }];
    const today = startOfDay(now);
    const dueDay = startOfDay(due);
    const msPerDay = 24 * 60 * 60 * 1000;
    const dayDelta = Math.round((dueDay.getTime() - today.getTime()) / msPerDay);
    if (dayDelta < 0) return [{ key: 'due:overdue', label: 'Overdue', order: 0 }];
    if (dayDelta === 0) return [{ key: 'due:today', label: 'Due today', order: 1 }];
    if (dayDelta <= 7) return [{ key: 'due:soon', label: 'Due this week', order: 2 }];
    return [{ key: 'due:later', label: 'Due later', order: 3 }];
  }
  if (groupBy === 'project') {
    const projects = [...(entity.projects || [])].sort((a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: 'base' }));
    if (projects.length === 0) return [{ key: 'project:none', label: 'No project', order: Number.MAX_SAFE_INTEGER }];
    return projects.map((project, index) => ({
      key: `project:${project.id}`,
      label: project.title,
      order: index,
    }));
  }
  if (groupBy === 'area') {
    const areas = [...(entity.areas || [])].sort((a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: 'base' }));
    if (areas.length === 0) return [{ key: 'area:none', label: 'No area', order: Number.MAX_SAFE_INTEGER }];
    return areas.map((area, index) => ({
      key: `area:${area.id}`,
      label: area.title,
      order: index,
    }));
  }
  if (groupBy === 'person') {
    const people = [...(entity.people || [])].sort((a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: 'base' }));
    if (people.length === 0) return [{ key: 'person:none', label: 'Unassigned', order: Number.MAX_SAFE_INTEGER }];
    return people.map((person, index) => ({
      key: `person:${person.id}`,
      label: person.title,
      order: index,
    }));
  }
  return [{ key: 'all', label: '', order: 0 }];
}

function groupTasks(entities, groupBy) {
  if (groupBy === 'none') return [];
  const groups = new Map();
  const metadata = new Map();
  entities.forEach((entity) => {
    taskGroupDescriptors(entity, groupBy).forEach((descriptor) => {
      if (!groups.has(descriptor.key)) groups.set(descriptor.key, []);
      groups.get(descriptor.key).push(entity);
      if (!metadata.has(descriptor.key)) metadata.set(descriptor.key, descriptor);
    });
  });
  return [...groups.entries()]
    .map(([key, items]) => ({ key, label: metadata.get(key)?.label || key, order: metadata.get(key)?.order ?? 0, items }))
    .sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      return a.label.localeCompare(b.label, undefined, { sensitivity: 'base' });
    });
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
  const [listLoading, setListLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState(false);
  const _init = loadListState(type);
  const [sortField, setSortField] = useState(_init?.sortField ?? 'updated');
  const [sortDir, setSortDir] = useState(_init?.sortDir ?? 'desc');
  const [statusFilter, setStatusFilter] = useState(_init?.statusFilter ?? []);
  const [priorityFilter, setPriorityFilter] = useState(_init?.priorityFilter ?? '');
  const [lifecycleFilter, setLifecycleFilter] = useState(parseLifetime(_init?.lifecycleFilter));
  const [groupBy, setGroupBy] = useState(type === 'task' ? (_init?.groupBy ?? 'none') : 'none');
  const [loadedStateType, setLoadedStateType] = useState(type);

  useEffect(() => {
    const next = loadListState(type);
    setSortField(next?.sortField ?? 'updated');
    setSortDir(next?.sortDir ?? 'desc');
    setStatusFilter(next?.statusFilter ?? []);
    setPriorityFilter(next?.priorityFilter ?? '');
    setLifecycleFilter(parseLifetime(next?.lifecycleFilter));
    setGroupBy(type === 'task' ? (next?.groupBy ?? 'none') : 'none');
    setLoadedStateType(type);
  }, [type]);

  useEffect(() => {
    let active = true;
    const params = { type, limit: 100 };
    if (lifecycleFilter && lifecycleFilter !== 'all') params.lifecycle = lifecycleFilter;
    setListLoading(true);
    v4API.entities.list(params)
      .then((response) => {
        if (active) {
          setEntities(response.data || []);
          setListLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err.message);
          setListLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [type, lifecycleFilter]);

  // Persist sort/filter state on every change.
  useEffect(() => {
    if (loadedStateType !== type) return;
    persistListState(type, {
      sortField, sortDir, statusFilter, priorityFilter, lifecycleFilter, groupBy,
    });
  }, [type, loadedStateType, sortField, sortDir, statusFilter, priorityFilter, lifecycleFilter, groupBy]);

  const statusOptions = STATUS_BY_TYPE[type] || [];
  const showsLifecycleControl = !SIMPLE_ARCHIVE_TYPES.has(type);

  const visibleEntities = useMemo(() => {
    let list = entities;
    if (statusFilter.length > 0) list = list.filter((e) => statusFilter.includes(e.status));
    if (priorityFilter) {
      list = list.filter((e) => {
        const p = e.properties?.priority || '';
        return priorityFilter === '__none__' ? !p : p === priorityFilter;
      });
    }
    return sortEntities(list, sortField, sortDir);
  }, [entities, statusFilter, priorityFilter, sortField, sortDir]);
  const taskGroups = useMemo(
    () => (type === 'task' ? groupTasks(visibleEntities, groupBy) : []),
    [type, visibleEntities, groupBy],
  );

  function toggleSortDir() {
    setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
  }

  function onSortFieldChange(value) {
    const next = SORT_FIELDS.find((f) => f.value === value);
    setSortField(value);
    if (next) setSortDir(next.defaultDir);
  }

  function toggleStatusFilter(value) {
    setStatusFilter((current) => (
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value]
    ));
  }

  function handleStatusToggle(value) {
    if (SIMPLE_ARCHIVE_TYPES.has(type) && value === 'archived') {
      setLifecycleFilter((current) => (current === 'archived' ? 'active' : 'archived'));
      setStatusFilter((current) => (
        current.includes(value)
          ? current.filter((item) => item !== value)
          : [value]
      ));
      return;
    }

    if (SIMPLE_ARCHIVE_TYPES.has(type) && lifecycleFilter === 'archived') {
      setLifecycleFilter('active');
      setStatusFilter((current) => {
        const next = current.includes(value)
          ? current.filter((item) => item !== value)
          : [...current.filter((item) => item !== 'archived'), value];
        return next;
      });
      return;
    }

    toggleStatusFilter(value);
  }

  function clearFilters() {
    setStatusFilter([]);
    setPriorityFilter('');
    setLifecycleFilter('active');
  }

  const activeFilterCount = [statusFilter.length > 0, priorityFilter, lifecycleFilter !== 'active'].filter(Boolean).length;
  const primaryActionLabel = open ? `Close new ${type}` : `New ${type}`;
  const isCompactList = type === 'person' || type === 'area';

  function renderEntityCard(entity) {
    const created = formatShortDate(entity.created_at);
    const updated = formatShortDate(entity.updated_at);
    const due = formatShortDate(entity.due_at);
    const isOverdue = entity.due_at && new Date(entity.due_at).getTime() < Date.now()
      && entity.status !== 'done' && entity.status !== 'completed' && entity.status !== 'cancelled';
    const linkedCounts = entity.linked_counts || {};
    const compactChips = type === 'area'
      ? [
          { key: 'projects', label: linkedCountLabel(linkedCounts.projects || 0, 'project') },
          { key: 'tasks', label: linkedCountLabel(linkedCounts.tasks || 0, 'task') },
          { key: 'notes', label: linkedCountLabel(linkedCounts.notes || 0, 'note') },
        ]
      : [
          { key: 'tasks', label: linkedCountLabel(linkedCounts.tasks || 0, 'task') },
          { key: 'projects', label: linkedCountLabel(linkedCounts.projects || 0, 'project') },
          { key: 'notes', label: linkedCountLabel(linkedCounts.notes || 0, 'note') },
        ];
    return (
      <li key={entity.id} className={`cardActionsParent ${isCompactList ? styles.compactCard : ''}`}>
        <CardActions
          entity={entity}
          onChanged={() => setEntities((cur) => cur.filter((e) => e.id !== entity.id))}
        />
        <Link to={detailPath(entity)} state={fromState}>
          <strong>{entity.title || 'Untitled'}</strong>
          {!isCompactList && entity.content && (
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
            {!isCompactList && created && (
              <span className={styles.mutedMeta} title={`Created ${created}`}>
                Created {created}
              </span>
            )}
            {isCompactList && updated && (
              <span className={styles.mutedMeta} title={`Updated ${updated}`}>
                Updated {updated}
              </span>
            )}
          </span>
          {isCompactList && (
            <span className={styles.countRow}>
              {compactChips.map((chip) => (
                <span key={chip.key} className={styles.countChip}>{chip.label}</span>
              ))}
            </span>
          )}
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
        {type === 'project' && entity.task_counts && (
          <span className={styles.taskCountBadge}>
            <span>{entity.task_counts.open}</span> open / {entity.task_counts.total} total
          </span>
        )}
        {type === 'task' && (entity.projects || []).length > 0 && (
          <span className={styles.cardTagRow}>
            {entity.projects.map((project) => (
              <Link
                key={project.id}
                to={`/projects/${project.id}`}
                className={styles.projectChip}
                title={`Project: ${project.title}`}
                onClick={(e) => e.stopPropagation()}
              >
                ▣ {project.title}
              </Link>
            ))}
          </span>
        )}
        {type === 'task' && (entity.areas || []).length > 0 && (
          <span className={styles.cardTagRow}>
            {entity.areas.map((area) => (
              <Link
                key={area.id}
                to={`/areas/${area.id}`}
                className={styles.projectChip}
                title={`Area: ${area.title}`}
                onClick={(e) => e.stopPropagation()}
              >
                ◫ {area.title}
              </Link>
            ))}
          </span>
        )}
        {type === 'task' && (entity.people || []).length > 0 && (
          <span className={styles.cardTagRow}>
            {entity.people.map((person) => (
              <Link
                key={person.id}
                to={`/people/${person.id}`}
                className={styles.projectChip}
                title={`Assignee: ${person.title}`}
                onClick={(e) => e.stopPropagation()}
              >
                @ {person.title}
              </Link>
            ))}
          </span>
        )}
      </li>
    );
  }

  async function handleCreate(event) {
    event.preventDefault();
    const trimmedTitle = title.trim();
    const trimmedContent = content.trim();
    if (type === 'note' ? !trimmedTitle && !trimmedContent : !trimmedTitle) return;
    setCreating(true);
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
      setCreating(false);
    }
  }

  return (
    <main className={styles.screen}>
      <section className={styles.listHeaderPanel}>
        <div className={styles.listHeaderTop}>
          <div className={styles.listTitleBlock}>
            <div className={styles.listTitleRow}>
              <h1>{pluralTitle[type]}</h1>
              <span className={styles.countPill}>{visibleEntities.length}{activeFilterCount > 0 && entities.length !== visibleEntities.length ? ` / ${entities.length}` : ''}</span>
              {activeFilterCount > 0 ? (
                <span className={styles.listFilterSummary}>
                  {activeFilterCount} active filter{activeFilterCount === 1 ? '' : 's'}
                </span>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            className={`${styles.addButton} ${open ? styles.addButtonActive : ''}`}
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={primaryActionLabel}
            title={primaryActionLabel}
          >
            {open
              ? <X size={14} strokeWidth={2.2} aria-hidden="true" />
              : <Plus size={14} strokeWidth={2.2} aria-hidden="true" />}
            <span>{open ? 'Close' : `New ${type}`}</span>
          </button>
        </div>
        <div className={styles.listToolbar}>
          <div className={styles.toolbarGroup}>
            <span className={styles.sortLabel}>
              Status
              {statusFilter.length > 0 && <span className={styles.filterBadge}>{statusFilter.length}</span>}
            </span>
            <div className={styles.statusChipRow} aria-label={`Filter ${pluralTitle[type].toLowerCase()} by status`}>
              <button
                type="button"
                className={`${styles.filterChip} ${statusFilter.length === 0 ? styles.filterChipActive : ''}`}
                aria-pressed={statusFilter.length === 0}
                onClick={clearFilters}
              >
                All statuses
              </button>
              {statusOptions.map((status) => (
                <button
                  key={status}
                  type="button"
                  className={`${styles.filterChip} ${statusFilter.includes(status) ? styles.filterChipActive : ''}`}
                  aria-pressed={statusFilter.includes(status)}
                  onClick={() => handleStatusToggle(status)}
                >
                  {formatFilterLabel(status)}
                </button>
              ))}
            </div>
          </div>
          <div className={styles.toolbarGroup}>
            <div className={styles.toolbarGroupHeader}>
              <span className={styles.sortLabel}>Refine</span>
              {activeFilterCount > 0 && (
                <button
                  type="button"
                  className={styles.clearFiltersButton}
                  onClick={clearFilters}
                >
                  Clear
                </button>
              )}
            </div>
            <div className={styles.toolbarControlRow}>
              {type === 'task' && (
                <label className={styles.filterControl}>
                  <span className={styles.controlLabel}>Priority</span>
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
              {type === 'task' && (
                <label className={styles.filterControl}>
                  <span className={styles.controlLabel}>Group</span>
                  <select
                    value={groupBy}
                    onChange={(event) => setGroupBy(event.target.value)}
                    aria-label="Group tasks by"
                  >
                    {TASK_GROUP_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </label>
              )}
              {showsLifecycleControl && (
                <label className={styles.filterControl}>
                  <span className={styles.controlLabel}>Lifecycle</span>
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
              )}
              <label className={`${styles.filterControl} ${styles.sortFieldControl}`}>
                <span className={styles.controlLabel}>Sort</span>
                <span className={styles.sortControl}>
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
                </span>
              </label>
            </div>
          </div>
        </div>
        {activeFilterCount > 0 && (
          <div className={styles.listFilterRail}>
            <span className={styles.listFilterRailLabel}>Active</span>
            <div className={styles.activeFiltersRow} aria-label="Active filters">
              {statusFilter.map((status) => (
                <button
                  key={status}
                  type="button"
                  className={styles.activeFilterPill}
                  onClick={() => toggleStatusFilter(status)}
                  title={`Remove ${formatFilterLabel(status)} filter`}
                >
                  Status: {formatFilterLabel(status)}
                  <X size={12} strokeWidth={2.2} aria-hidden="true" />
                </button>
              ))}
              {priorityFilter && (
                <button
                  type="button"
                  className={styles.activeFilterPill}
                  onClick={() => setPriorityFilter('')}
                  title="Remove priority filter"
                >
                  Priority: {priorityFilter === '__none__' ? 'none' : priorityFilter}
                  <X size={12} strokeWidth={2.2} aria-hidden="true" />
                </button>
              )}
              {showsLifecycleControl && lifecycleFilter !== 'active' && (
                <button
                  type="button"
                  className={styles.activeFilterPill}
                  onClick={() => setLifecycleFilter('active')}
                  title="Reset lifecycle filter"
                >
                  Lifecycle: {lifecycleFilter}
                  <X size={12} strokeWidth={2.2} aria-hidden="true" />
                </button>
              )}
            </div>
          </div>
        )}
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
            <button className={styles.primaryButton} type="submit" disabled={creating || (type === 'note' ? !title.trim() && !content.trim() : !title.trim())}>
              {creating ? 'Creating...' : `Create ${type}`}
            </button>
          </form>
        )}
        {error && <div className={styles.error}>{error}</div>}
      </section>

      <section className={styles.listPanel}>
        {listLoading ? (
          <p className={styles.emptyText}>Loading {pluralTitle[type].toLowerCase()}...</p>
        ) : visibleEntities.length === 0 ? (
          <p className={styles.emptyText}>
            {entities.length === 0
              ? `No ${pluralTitle[type].toLowerCase()} yet.`
              : `No ${pluralTitle[type].toLowerCase()} match the current filters.`}
          </p>
        ) : (
          type === 'task' && groupBy !== 'none' ? (
            <div className={styles.groupedList}>
              {taskGroups.map((group) => (
                <section key={group.key} className={styles.groupSection}>
                  <div className={styles.groupHeader}>
                    <h2>{group.label}</h2>
                    <span className={styles.countPill}>{group.items.length}</span>
                  </div>
                  <ul className={styles.cards}>
                    {group.items.map((entity) => renderEntityCard(entity))}
                  </ul>
                </section>
              ))}
            </div>
          ) : (
            <ul className={`${styles.cards} ${isCompactList ? styles.compactCards : ''}`}>
              {visibleEntities.map((entity) => renderEntityCard(entity))}
            </ul>
          )
        )}
      </section>
    </main>
  );
}
