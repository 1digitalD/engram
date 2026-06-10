/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Archive, ChevronDown, ChevronRight, Plus, RefreshCw, Save, Trash2, X } from 'lucide-react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import MarkdownContent from '../components/MarkdownContent';
import MarkdownEditor from '../components/MarkdownEditor';
import styles from './V4EntityScreens.module.css';

const statusOptions = {
  note: ['active', 'processed', 'archived'],
  task: ['open', 'in_progress', 'waiting', 'blocked', 'done', 'cancelled'],
  project: ['active', 'on_hold', 'completed', 'cancelled'],
  area: ['active', 'archived'],
  person: ['active', 'archived'],
  resource: ['active', 'archived'],
};

const priorityOptions = ['', 'low', 'medium', 'high', 'urgent'];

const actionConfigs = {
  project: [
    { key: 'area', sectionKeys: ['area'], title: 'Area', type: 'area', relationship: 'parent', direction: 'outgoing', primary: 'Create new area', existing: 'Move/link to area', size: 'narrow' },
    { key: 'task', sectionKeys: ['open_tasks', 'completed_tasks'], title: 'Tasks', type: 'task', relationship: 'parent', direction: 'incoming', primary: 'Add new task', existing: 'Add existing task', taskFields: true },
    { key: 'note', sectionKeys: ['notes'], title: 'Notes', type: 'note', relationship: 'related', direction: 'outgoing', primary: 'Add project note', existing: 'Link existing note' },
    { key: 'person', sectionKeys: ['people'], title: 'People', type: 'person', relationship: 'assigned_to', direction: 'outgoing', primary: 'Add new person', existing: 'Add existing person', size: 'narrow' },
    { key: 'resource', sectionKeys: ['resources'], title: 'Resources', type: 'resource', relationship: 'references', direction: 'outgoing', primary: 'Add new resource', existing: 'Add existing resource' },
  ],
  area: [
    { key: 'project', sectionKeys: ['projects'], title: 'Projects', type: 'project', relationship: 'parent', direction: 'incoming', primary: 'Add new project', existing: 'Add existing project' },
    { key: 'task', sectionKeys: ['tasks'], title: 'Tasks', type: 'task', relationship: 'parent', direction: 'incoming', primary: 'Add new task', existing: 'Add existing task', taskFields: true },
    { key: 'note', sectionKeys: ['notes'], title: 'Notes', type: 'note', relationship: 'related', direction: 'outgoing', primary: 'Add area note', existing: 'Link existing note' },
    { key: 'resource', sectionKeys: ['resources'], title: 'Resources', type: 'resource', relationship: 'references', direction: 'outgoing', primary: 'Add new resource', existing: 'Add existing resource' },
  ],
  task: [
    { key: 'project', sectionKeys: ['project'], title: 'Project', type: 'project', relationship: 'parent', direction: 'outgoing', primary: 'Create new project', existing: 'Move/link to project' },
    { key: 'area', sectionKeys: ['area'], title: 'Area', type: 'area', relationship: 'parent', direction: 'outgoing', primary: 'Create new area', existing: 'Move/link to area', size: 'narrow' },
    { key: 'person', sectionKeys: ['people_mentioned'], title: 'People', type: 'person', relationship: 'mentions', direction: 'outgoing', existing: 'Link existing person', size: 'narrow' },
    { key: 'note', sectionKeys: ['source_notes', 'related_notes'], title: 'Notes', type: 'note', relationship: 'derived_from', direction: 'outgoing', primary: 'Add source note', existing: 'Attach existing note' },
    { key: 'resource', sectionKeys: ['resources'], title: 'Resources', type: 'resource', relationship: 'references', direction: 'outgoing', primary: 'Add resource', existing: 'Attach existing resource' },
    { key: 'blocker', sectionKeys: ['blocking'], title: 'Blocked By', type: 'task', relationship: 'blocks', direction: 'incoming', primary: 'Create blocking task', existing: 'Add blocking task', taskFields: true },
  ],
  note: [
    { key: 'task', sectionKeys: ['derived_tasks'], title: 'Derived Tasks', type: 'task', relationship: 'derived_from', direction: 'incoming', primary: 'Create task from note', existing: 'Link existing task', taskFields: true },
    { key: 'project', sectionKeys: ['projects'], title: 'Projects', type: 'project', relationship: 'related', direction: 'outgoing', primary: 'Add new project', existing: 'Link existing project' },
    { key: 'area', sectionKeys: ['areas'], title: 'Areas', type: 'area', relationship: 'related', direction: 'outgoing', existing: 'Link existing area', size: 'narrow' },
    { key: 'person', sectionKeys: ['people_mentioned'], title: 'People Mentioned', type: 'person', relationship: 'mentions', direction: 'outgoing', primary: 'Add mentioned person', existing: 'Link existing person', size: 'narrow' },
    { key: 'resource', sectionKeys: ['referenced_resources'], title: 'Referenced Resources', type: 'resource', relationship: 'references', direction: 'outgoing', primary: 'Add referenced resource', existing: 'Link existing resource' },
  ],
  person: [
    { key: 'task', sectionKeys: ['assigned_tasks'], title: 'Assigned Tasks', type: 'task', relationship: 'assigned_to', direction: 'incoming', primary: 'Add assigned task', existing: 'Assign existing task', taskFields: true },
    { key: 'note', sectionKeys: ['mentioned_in_notes'], title: 'Notes', type: 'note', relationship: 'mentions', direction: 'incoming', primary: 'Add note about person', existing: 'Link existing note' },
    { key: 'project', sectionKeys: ['projects'], title: 'Projects', type: 'project', relationship: 'assigned_to', direction: 'incoming', primary: 'Create new project', existing: 'Add to existing project' },
    { key: 'resource', sectionKeys: ['resources'], title: 'Resources', type: 'resource', relationship: 'references', direction: 'outgoing', primary: 'Add person resource', existing: 'Link existing resource' },
  ],
  resource: [
    { key: 'note', sectionKeys: ['referenced_by_notes'], title: 'Reference Notes', type: 'note', relationship: 'references', direction: 'incoming', primary: 'Add reference note', existing: 'Link existing note' },
    { key: 'project', sectionKeys: ['projects'], title: 'Projects', type: 'project', relationship: 'references', direction: 'incoming', primary: 'Create new project', existing: 'Use in existing project' },
    { key: 'task', sectionKeys: ['tasks'], title: 'Tasks', type: 'task', relationship: 'references', direction: 'incoming', primary: 'Create new task', existing: 'Use in existing task', taskFields: true },
    { key: 'area', sectionKeys: ['areas'], title: 'Areas', type: 'area', relationship: 'references', direction: 'incoming', primary: 'Create new area', existing: 'Use in existing area', size: 'narrow' },
    { key: 'person', sectionKeys: ['people'], title: 'People', type: 'person', relationship: 'references', direction: 'incoming', primary: 'Add new person', existing: 'Link existing person', size: 'narrow' },
  ],
};

function pathForEntity(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function collectionPathForType(entityType) {
  return entityType === 'person' ? '/people' : `/${entityType}s`;
}

function toInputDateTime(value) {
  if (!value) return '';
  return value.slice(0, 16);
}

function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString();
}

function humanizeToken(value) {
  if (!value) return '';
  return String(value).replace(/_/g, ' ').replace(/:/g, ' · ');
}

function formatConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value) || value <= 0) return '';
  return `${Math.round(value * 100)}% confidence`;
}

function buildDraft(entity) {
  return {
    title: entity.title || '',
    content: entity.content || '',
    status: entity.status || 'active',
    due_at: toInputDateTime(entity.due_at),
    follow_up_at: toInputDateTime(entity.follow_up_at),
    reference_url: entity.reference_url || '',
    tags: (entity.tags || []).map((tag) => tag.name),
    priority: entity.properties?.priority || '',
  };
}

function eventTitle(event) {
  const labels = {
    created: 'Created',
    updated: 'Updated',
    status_changed: 'Status changed',
    archived: 'Archived',
    deleted: 'Deleted',
    relationship_added: 'Relationship added',
    relationship_updated: 'Relationship updated',
    relationship_removed: 'Relationship removed',
    tag_added: 'Tag added',
    tag_removed: 'Tag removed',
    ai_processed: 'AI processed',
    ai_updated: 'AI updated',
    suggestion_accepted: 'Suggestion accepted',
    suggestion_dismissed: 'Suggestion dismissed',
    activity_update_added: 'Activity update added',
    reverted: 'Reverted',
  };
  return labels[event.event_type] || humanizeToken(event.event_type);
}

function eventReason(event) {
  if (event.reason) return event.reason;
  if (event.event_type === 'status_changed') {
    const from = event.old_value?.status;
    const to = event.new_value?.status;
    if (from && to) return `${humanizeToken(from)} -> ${humanizeToken(to)}`;
  }
  if (event.event_type === 'updated') {
    const ignoredKeys = new Set(['id', 'created_at', 'updated_at', 'relationship_counts']);
    const changedKeys = [
      ...new Set([
        ...Object.keys(event.old_value || {}),
        ...Object.keys(event.new_value || {}),
      ]),
    ].filter((key) => (
      !ignoredKeys.has(key)
      && JSON.stringify(event.old_value?.[key]) !== JSON.stringify(event.new_value?.[key])
    ));

    if (changedKeys.length === 0) return '';
    if (changedKeys.length === 1 && changedKeys[0] === 'status') return '';

    const labels = changedKeys.map((key) => {
      if (key === 'follow_up_at') return 'follow-up';
      if (key === 'due_at') return 'due date';
      if (key === 'reference_url') return 'reference URL';
      if (key === 'properties') {
        const propertyKeys = [
          ...new Set([
            ...Object.keys(event.old_value?.properties || {}),
            ...Object.keys(event.new_value?.properties || {}),
          ]),
        ].filter((propertyKey) => (
          JSON.stringify(event.old_value?.properties?.[propertyKey]) !== JSON.stringify(event.new_value?.properties?.[propertyKey])
        ));
        return propertyKeys.length ? propertyKeys.map(humanizeToken).join(', ') : 'properties';
      }
      return humanizeToken(key);
    });

    return `changed · ${labels.join(', ')}`;
  }
  if (event.event_type === 'relationship_added' || event.event_type === 'relationship_updated') {
    const relationship = event.new_value?.relationship_type;
    if (relationship) return `relationship · ${humanizeToken(relationship)}`;
  }
  if (event.event_type === 'tag_added' && event.new_value?.name) {
    return `tag · ${event.new_value.name}`;
  }
  return '';
}

function shouldShowEvent(event) {
  if (!event) return false;
  if (event.event_type !== 'updated') return true;
  return Boolean(eventReason(event));
}

function cleanPayload(payload) {
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== '' && value !== undefined));
}

function relationshipPayload(currentId, linkedId, config) {
  if (config.direction === 'incoming') {
    return { sourceId: linkedId, target_entity_id: currentId, relationship_type: config.relationship };
  }
  return { sourceId: currentId, target_entity_id: linkedId, relationship_type: config.relationship };
}

function sectionItems(detail, key) {
  return detail.sections.find((section) => section.key === key)?.items || [];
}

function backLabel(from, entityType) {
  const fallback = collectionPathForType(entityType);
  const target = from || fallback;
  if (target === '/') return 'Back to Home';
  if (target.startsWith('/today')) return 'Back to Today';
  if (target.startsWith('/inbox')) return 'Back to Inbox';
  if (target.startsWith('/suggestions')) return 'Back to Suggestions';
  if (target.startsWith('/search')) return 'Back to Search';
  if (target.startsWith('/notes')) return 'Back to Notes';
  if (target.startsWith('/projects')) return 'Back to Projects';
  if (target.startsWith('/tasks')) return 'Back to Tasks';
  if (target.startsWith('/areas')) return 'Back to Areas';
  if (target.startsWith('/people')) return 'Back to People';
  if (target.startsWith('/resources')) return 'Back to Resources';
  return 'Back';
}

function CollapsibleSection({
  ariaLabel,
  className,
  headerClassName,
  title,
  eyebrow,
  meta,
  actions,
  defaultExpanded = true,
  canCollapse = true,
  children,
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <section
      className={[
        className,
        !expanded ? styles.collapsibleSectionCollapsed : '',
      ].filter(Boolean).join(' ')}
      aria-label={ariaLabel}
    >
      <header className={headerClassName}>
        <div>
          {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
          <h2>{title}</h2>
        </div>
        <div className={styles.segmentHeaderRight}>
          {meta || null}
          {actions || null}
          {canCollapse ? (
            <button
              type="button"
              className={styles.collapseButton}
              onClick={() => setExpanded((value) => !value)}
              aria-expanded={expanded}
              aria-label={`${expanded ? 'Collapse' : 'Expand'} ${title}`}
              title={expanded ? 'Collapse section' : 'Expand section'}
            >
              {expanded ? <ChevronDown size={14} strokeWidth={2.4} aria-hidden="true" /> : <ChevronRight size={14} strokeWidth={2.4} aria-hidden="true" />}
              <span>{expanded ? 'Collapse' : 'Expand'}</span>
            </button>
          ) : null}
        </div>
      </header>
      {expanded ? children : null}
    </section>
  );
}

export default function V4EntityDetail({ type: routeType }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [detail, setDetail] = useState(null);
  const [draft, setDraft] = useState({
    title: '',
    content: '',
    status: 'active',
    due_at: '',
    follow_up_at: '',
    reference_url: '',
    tags: [],
    priority: '',
  });
  const [error, setError] = useState('');
  const [events, setEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState('');
  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessStatus, setReprocessStatus] = useState('');
  const [saveStatus, setSaveStatus] = useState('');

  function applyDetailResponse(response) {
    setDetail(response);
    setError('');
    setDraft(buildDraft(response.entity));
  }

  async function loadDetail() {
    setEventsLoading(true);
    const [detailResponse, eventsResponse] = await Promise.allSettled([
      v4API.entities.detail(id),
      v4API.entities.events(id),
    ]);
    if (detailResponse.status !== 'fulfilled') {
      throw detailResponse.reason;
    }
    applyDetailResponse(detailResponse.value);
    if (eventsResponse.status === 'fulfilled') {
      setEvents(eventsResponse.value.data || []);
      setEventsError('');
    } else {
      setEvents([]);
      setEventsError(eventsResponse.reason?.message || 'Failed to load history');
    }
    setEventsLoading(false);
  }

  useEffect(() => {
    let active = true;
    setEventsLoading(true);
    Promise.allSettled([
      v4API.entities.detail(id),
      v4API.entities.events(id),
    ])
      .then(([detailResponse, eventsResponse]) => {
        if (!active) return;
        if (detailResponse.status !== 'fulfilled') {
          setError(detailResponse.reason?.message || 'Failed to load entity');
          setEventsLoading(false);
          return;
        }
        applyDetailResponse(detailResponse.value);
        if (eventsResponse.status === 'fulfilled') {
          setEvents(eventsResponse.value.data || []);
          setEventsError('');
        } else {
          setEvents([]);
          setEventsError(eventsResponse.reason?.message || 'Failed to load history');
        }
        setEventsLoading(false);
      })
      .catch((err) => {
        if (active) {
          setError(err.message);
          setEventsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [id]);

  async function handleSave(event) {
    event.preventDefault();
    setError('');
    setSaveStatus('');
    const properties = { ...(detail.entity.properties || {}) };
    if (draft.priority) {
      properties.priority = draft.priority;
    } else {
      delete properties.priority;
    }

    try {
      await v4API.entities.update(id, cleanPayload({
        title: draft.title,
        content: draft.content,
        status: draft.status,
        due_at: draft.due_at,
        follow_up_at: draft.follow_up_at,
        reference_url: draft.reference_url,
        properties,
        tags: Array.isArray(draft.tags) ? draft.tags : [],
      }));
      await loadDetail();
      setSaveStatus('Saved');
    } catch (err) {
      setError(err.message || 'Failed to save entity');
    }
  }

  function navigateBack(fallback) {
    const from = location.state?.from;
    if (from && typeof from === 'string') {
      navigate(from);
    } else {
      navigate(fallback);
    }
  }

  async function handleArchive() {
    setError('');
    try {
      await v4API.entities.update(id, { lifecycle: 'archived' });
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to archive entity');
    }
  }

  async function handleDelete() {
    setError('');
    try {
      await v4API.entities.delete(id);
      navigateBack(collectionPathForType(entity.type));
    } catch (err) {
      setError(err.message || 'Failed to delete entity');
    }
  }

  async function handleRemoveRelationship(relationshipId) {
    setError('');
    try {
      await v4API.relationships.delete(relationshipId);
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to remove relationship');
    }
  }

  async function handleCreateAndLink(config, form) {
    setError('');
    try {
      const properties = {};
      if (form.priority) properties.priority = form.priority;
      const response = config.type === 'note'
        ? await v4API.capture({
          title: form.title || undefined,
          content: form.content || form.title,
          source: 'ui',
          mode: 'auto',
        })
        : await v4API.entities.create(cleanPayload({
          type: config.type,
          title: form.title,
          content: form.content,
          due_at: form.due_at,
          follow_up_at: form.follow_up_at,
          properties,
        }));
      const createdEntity = config.type === 'note' ? response.source_note : response.data;
      const link = relationshipPayload(id, createdEntity.id, config);
      await v4API.relationships.create(link.sourceId, {
        target_entity_id: link.target_entity_id,
        relationship_type: link.relationship_type,
      });
      await loadDetail();
    } catch (err) {
      setError(err.message || `Failed to add ${config.type}`);
    }
  }

  async function handleLinkExisting(config, targetId) {
    if (!targetId) return;
    setError('');
    try {
      const link = relationshipPayload(id, targetId, config);
      await v4API.relationships.create(link.sourceId, {
        target_entity_id: link.target_entity_id,
        relationship_type: link.relationship_type,
      });
      await loadDetail();
    } catch (err) {
      setError(err.message || `Failed to link ${config.type}`);
    }
  }

  async function handleReprocess() {
    setError('');
    setReprocessStatus('Re-running AI extraction…');
    setReprocessing(true);
    try {
      const result = await v4API.reprocess(id);
      await loadDetail();
      const applied = (result?.applied_changes || []).length;
      const suggested = (result?.suggestions || []).length;
      const parts = [];
      if (applied) parts.push(`${applied} change${applied === 1 ? '' : 's'} applied`);
      if (suggested) parts.push(`${suggested} suggestion${suggested === 1 ? '' : 's'}`);
      setReprocessStatus(parts.length ? `Re-ran extraction · ${parts.join(' · ')}` : 'Re-ran extraction · no changes');
      setTimeout(() => setReprocessStatus(''), 4500);
    } catch (err) {
      setReprocessStatus('');
      setError(err.message || 'Failed to reprocess note');
    } finally {
      setReprocessing(false);
    }
  }

  async function handleQuickStatus(entityId, status) {
    setError('');
    try {
      await v4API.entities.update(entityId, { status });
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to update status');
    }
  }

  if (!detail) {
    return (
      <main className={styles.screen}>
        <section className={styles.panel}>
          <p>{error || 'Loading entity...'}</p>
        </section>
      </main>
    );
  }

  const entity = detail.entity;
  const entityType = routeType || entity.type;
  const backTarget = location.state?.from || collectionPathForType(entity.type);
  const showDueDate = entity.type !== 'note';
  const configs = actionConfigs[entity.type] || [];
  const usedSectionKeys = new Set(configs.flatMap((config) => config.sectionKeys || []));
  const additionalSections = detail.sections.filter((section) => !usedSectionKeys.has(section.key) && section.items.length > 0);
  const currentTags = (entity.tags || []).map((tag) => tag.name);
  const entityPriority = entity.properties?.priority || '';
  const isDirty = (
    draft.title !== (entity.title || '')
    || draft.content !== (entity.content || '')
    || draft.status !== (entity.status || 'active')
    || draft.due_at !== toInputDateTime(entity.due_at)
    || draft.follow_up_at !== toInputDateTime(entity.follow_up_at)
    || draft.reference_url !== (entity.reference_url || '')
    || draft.priority !== entityPriority
    || JSON.stringify(draft.tags) !== JSON.stringify(currentTags)
  );

  return (
    <main className={styles.screen}>
      <section className={styles.headerPanel}>
        <form onSubmit={handleSave} className={styles.detailForm} aria-label="Edit entity">
          <div className={styles.headerTop}>
            <div className={styles.headerContext}>
              <button
                type="button"
                className={styles.backLink}
                onClick={() => navigateBack(collectionPathForType(entity.type))}
              >
                {backLabel(backTarget, entity.type)}
              </button>
              <p className={styles.eyebrow}>Engram v4 {entityType}</p>
            </div>
            <div className={styles.headerActions}>
              {entity.type === 'note' && (
                <button
                  className={`${styles.secondaryButton} ${styles.iconButton}`}
                  type="button"
                  onClick={handleReprocess}
                  disabled={reprocessing}
                  aria-label="Re-run AI extraction"
                  aria-busy={reprocessing}
                  title={reprocessing ? 'Re-running AI extraction…' : 'Re-run AI extraction'}
                >
                  <RefreshCw
                    size={16}
                    strokeWidth={2}
                    aria-hidden="true"
                    className={reprocessing ? 'spin' : undefined}
                  />
                </button>
              )}
              <button
                className={`${styles.secondaryButton} ${styles.iconButton}`}
                type="button"
                onClick={handleArchive}
                aria-label="Archive"
                title="Archive"
              >
                <Archive size={16} strokeWidth={2} aria-hidden="true" />
              </button>
              <button
                className={`${styles.dangerButton} ${styles.iconButton}`}
                type="button"
                onClick={handleDelete}
                aria-label="Delete"
                title="Delete"
              >
                <Trash2 size={16} strokeWidth={2} aria-hidden="true" />
              </button>
              <button
                className={`${styles.primaryButton} ${styles.iconButton}`}
                type="submit"
                aria-label="Save"
                title="Save"
                disabled={!isDirty}
              >
                <Save size={16} strokeWidth={2} aria-hidden="true" />
              </button>
            </div>
          </div>
          <div className={styles.detailEditorColumn}>
            <div className={styles.statusPriorityRow}>
              <div className={`${styles.pillSelect} ${styles[`statusDot_${draft.status}`] || ''}`}>
                <span className={styles.statusDot} aria-hidden="true" />
                <select
                  value={draft.status}
                  onChange={(event) => {
                    const next = event.target.value;
                    setDraft((current) => ({ ...current, status: next }));
                    setSaveStatus('');
                  }}
                  aria-label="Status"
                >
                  {(statusOptions[entity.type] || ['active']).map((status) => (
                    <option key={status} value={status}>{status}</option>
                  ))}
                </select>
              </div>
              <div className={`${styles.pillSelect} ${styles[`priorityDot_${draft.priority || 'none'}`] || ''}`}>
                <span className={styles.statusDot} aria-hidden="true" />
                <select
                  value={draft.priority}
                  onChange={(event) => {
                    const next = event.target.value;
                    setDraft((current) => ({ ...current, priority: next }));
                    setSaveStatus('');
                  }}
                  aria-label="Priority"
                >
                  {priorityOptions.map((priority) => (
                    <option key={priority || 'none'} value={priority}>
                      {priority || 'no priority'}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <InlineTextField
              value={draft.title}
              onChange={(val) => {
                setDraft((current) => ({ ...current, title: val }));
                setSaveStatus('');
              }}
              placeholder="Untitled"
              ariaLabel="Title"
              className={styles.detailTitle}
            />
            {(entity.ai?.summary || entity.ai?.entity_summary) && (
              <aside className={styles.aiSummary} aria-label="AI summary">
                <span className={styles.aiSummaryLabel}>AI summary</span>
                <p>{entity.ai?.entity_summary || entity.ai?.summary}</p>
              </aside>
            )}
            <InlineMarkdownField
              value={draft.content || ''}
              onChange={(val) => {
                setDraft((current) => ({ ...current, content: val }));
                setSaveStatus('');
              }}
              placeholder="Add a description — supports Markdown"
            />
            <footer className={styles.detailFooter}>
              <div className={styles.footerSection}>
                <span className={styles.footerLabel}>Tags</span>
                <TagsField
                  value={draft.tags}
                  onChange={(val) => {
                    setDraft((current) => ({ ...current, tags: val }));
                    setSaveStatus('');
                  }}
                />
              </div>
              <div className={styles.footerSection}>
                <span className={styles.footerLabel}>URL</span>
                <InlineTextField
                  value={draft.reference_url}
                  onChange={(val) => {
                    setDraft((current) => ({ ...current, reference_url: val }));
                    setSaveStatus('');
                  }}
                  placeholder="https://…"
                  ariaLabel="Reference URL"
                  type="url"
                  renderEmpty="Add URL"
                />
              </div>
              <div className={styles.footerDateGrid}>
                {showDueDate && (
                  <div className={styles.footerDate}>
                    <span className={styles.footerLabel}>Due</span>
                    <InlineDateField
                      value={draft.due_at}
                      onChange={(val) => {
                        setDraft((current) => ({ ...current, due_at: val }));
                        setSaveStatus('');
                      }}
                      ariaLabel="Due date"
                    />
                  </div>
                )}
                <div className={styles.footerDate}>
                  <span className={styles.footerLabel}>Follow-up</span>
                  <InlineDateField
                    value={draft.follow_up_at}
                    onChange={(val) => {
                      setDraft((current) => ({ ...current, follow_up_at: val }));
                      setSaveStatus('');
                    }}
                    ariaLabel="Follow-up date"
                  />
                </div>
                <div className={styles.footerDate}>
                  <span className={styles.footerLabel}>Created</span>
                  <span className={`${styles.metaStaticChip} ${styles.readOnlyChip}`} title="Not editable">{formatDateTime(entity.created_at)}</span>
                </div>
                <div className={styles.footerDate}>
                  <span className={styles.footerLabel}>Updated</span>
                  <span className={`${styles.metaStaticChip} ${styles.readOnlyChip}`} title="Not editable">{formatDateTime(entity.updated_at)}</span>
                </div>
              </div>
            </footer>
          </div>
        </form>
        {(isDirty || saveStatus) && (
          <div className={styles.statusBanner} role="status" aria-live="polite">
            <span>{isDirty ? 'Unsaved changes' : saveStatus}</span>
          </div>
        )}
        {reprocessStatus && (
          <div className={styles.statusBanner} role="status" aria-live="polite">
            {reprocessing && <RefreshCw size={14} strokeWidth={2} className="spin" aria-hidden="true" />}
            <span>{reprocessStatus}</span>
          </div>
        )}
        {error && <div className={styles.error}>{error}</div>}
      </section>

      {['project', 'task', 'area'].includes(entity.type) && (
        <ActivityUpdatesSection entityId={entity.id} className={styles.fullWidthPanel} />
      )}

      {entity.type === 'project' && (
        <ProjectWorkspacePanel detail={detail} />
      )}

      {entity.type === 'task' && (
        <TaskWorkspacePanel entity={entity} detail={detail} />
      )}

      {entity.type === 'area' && (
        <AreaWorkspacePanel entity={entity} detail={detail} />
      )}

      {entity.type === 'person' && (
        <PersonWorkspacePanel entity={entity} detail={detail} />
      )}

      {entity.type === 'resource' && (
        <ResourceWorkspacePanel entity={entity} detail={detail} />
      )}

      {entity.type === 'note' && (
        <NoteWorkspacePanel entity={entity} detail={detail} />
      )}

      {entity.type === 'note' && (
        <CaptureChangesPanel entityId={entity.id} className={styles.fullWidthPanel} />
      )}

      <section className={styles.segmentsStack} aria-label={`${entityType} relationship segments`}>
        {configs.map((config) => (
          <RelationshipSegment
            key={config.key}
            config={config}
            currentId={entity.id}
            sections={detail.sections.filter((section) => (config.sectionKeys || []).includes(section.key))}
            onCreate={(form) => handleCreateAndLink(config, form)}
            onLink={(targetId) => handleLinkExisting(config, targetId)}
            onRemove={handleRemoveRelationship}
            onQuickStatus={handleQuickStatus}
          />
        ))}
        {additionalSections.length > 0 && (
          <RelationshipSegment
            config={{ key: 'additional', title: 'Additional Links' }}
            currentId={entity.id}
            sections={additionalSections}
            onRemove={handleRemoveRelationship}
            onQuickStatus={handleQuickStatus}
          />
        )}
        <EntityInspectionPanel
          entity={entity}
          events={events}
          loading={eventsLoading}
          error={eventsError}
        />
      </section>
    </main>
  );
}

function ProjectWorkspacePanel({ detail }) {
  const openTasks = sectionItems(detail, 'open_tasks');
  const completedTasks = sectionItems(detail, 'completed_tasks');
  const notes = sectionItems(detail, 'notes');
  const people = sectionItems(detail, 'people');
  const resources = sectionItems(detail, 'resources');
  const areaLinks = sectionItems(detail, 'area');
  const nextTask = openTasks.find((item) => ['open', 'in_progress'].includes(item.entity.status)) || openTasks[0] || null;
  const blockedOpenTasks = openTasks.filter((item) => ['blocked', 'waiting'].includes(item.entity.status));
  const allOpenTasksBlocked = openTasks.length > 0 && blockedOpenTasks.length === openTasks.length;

  const warnings = [];
  if (openTasks.length === 0) warnings.push('No open tasks');
  if (allOpenTasksBlocked) warnings.push('All open tasks are blocked or waiting');
  if (!detail.entity.follow_up_at && !detail.entity.due_at) warnings.push('No review date set');
  if (notes.length === 0) warnings.push('No project notes linked');
  if (areaLinks.length === 0) warnings.push('No area linked');

  return (
    <CollapsibleSection
      ariaLabel="Project workspace"
      className={`${styles.workspacePanel} ${styles.workspacePanelWarm}`}
      headerClassName={styles.workspaceHeader}
      eyebrow="Project workspace"
      title="Momentum at a glance"
      canCollapse={false}
      meta={(
        <div className={styles.workspaceStats}>
          <div className={styles.workspaceStat}>
            <strong>{openTasks.length}</strong>
            <span>open tasks</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{completedTasks.length}</strong>
            <span>completed</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{notes.length}</strong>
            <span>notes</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{people.length}</strong>
            <span>people</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{resources.length}</strong>
            <span>resources</span>
          </div>
        </div>
      )}
    >
      <div className={styles.workspaceGrid}>
        <section className={styles.workspaceCard}>
          <h3>Next step</h3>
          {nextTask ? (
            <Link to={pathForEntity(nextTask.entity)} className={styles.workspaceLinkCard}>
              <strong>{nextTask.entity.title || 'Untitled task'}</strong>
              <span className={styles.metaRow}>
                <span className={styles.statusPill}>{nextTask.entity.status}</span>
                {nextTask.entity.properties?.priority ? <span className={styles.priorityPill}>Priority {nextTask.entity.properties.priority}</span> : null}
              </span>
            </Link>
          ) : (
            <p className={styles.muted}>Add an open task to make the project actionable.</p>
          )}
        </section>

        <section className={styles.workspaceCard}>
          <h3>Coverage</h3>
          <div className={styles.workspaceCoverage}>
            <span className={styles.metaStaticChip}>{areaLinks.length > 0 ? `Area · ${areaLinks[0].entity.title}` : 'No area linked'}</span>
            <span className={styles.metaStaticChip}>{people.length} people linked</span>
            <span className={styles.metaStaticChip}>{notes.length} notes linked</span>
            <span className={styles.metaStaticChip}>{resources.length} resources linked</span>
          </div>
        </section>

        <section className={styles.workspaceCard}>
          <h3>Watchouts</h3>
          {warnings.length > 0 ? (
            <ul className={styles.workspaceWarnings}>
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>No obvious project hygiene gaps right now.</p>
          )}
        </section>
      </div>
    </CollapsibleSection>
  );
}

function TaskWorkspacePanel({ entity, detail }) {
  const projectLinks = sectionItems(detail, 'project');
  const areaLinks = sectionItems(detail, 'area');
  const people = sectionItems(detail, 'people');
  const sourceNotes = sectionItems(detail, 'source_notes');
  const relatedNotes = sectionItems(detail, 'related_notes');
  const resources = sectionItems(detail, 'resources');
  const blocking = sectionItems(detail, 'blocking');
  const relatedTasks = sectionItems(detail, 'related_tasks');

  const blockedBy = blocking.filter((item) => item.direction === 'incoming');
  const blocks = blocking.filter((item) => item.direction === 'outgoing');
  const currentOwner = people[0]?.entity || null;
  const currentProject = projectLinks[0]?.entity || null;
  const currentArea = areaLinks[0]?.entity || null;

  const warnings = [];
  if (!currentProject && !currentArea) warnings.push('No project or area linked');
  if (!currentOwner && entity.status === 'waiting') warnings.push('Waiting task has no owner linked');
  if (blockedBy.length > 0) warnings.push(`Blocked by ${blockedBy.length} task${blockedBy.length === 1 ? '' : 's'}`);
  if (!entity.follow_up_at && !entity.due_at && ['open', 'in_progress', 'waiting', 'blocked'].includes(entity.status)) warnings.push('No follow-up or due date set');
  if (sourceNotes.length === 0) warnings.push('No source note linked');

  return (
    <CollapsibleSection
      ariaLabel="Task workspace"
      className={`${styles.workspacePanel} ${styles.workspacePanelWarm}`}
      headerClassName={styles.workspaceHeader}
      eyebrow="Task workspace"
      title="Execution context"
      canCollapse={false}
      meta={(
        <div className={styles.workspaceStats}>
          <div className={styles.workspaceStat}>
            <strong>{blockedBy.length}</strong>
            <span>blocking now</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{sourceNotes.length + relatedNotes.length}</strong>
            <span>notes linked</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{resources.length}</strong>
            <span>resources</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{relatedTasks.length + blocks.length}</strong>
            <span>task links</span>
          </div>
        </div>
      )}
    >
      <div className={styles.workspaceGrid}>
        <section className={styles.workspaceCard}>
          <h3>Ownership and scope</h3>
          <div className={styles.workspaceCoverage}>
            <span className={styles.metaStaticChip}>{currentProject ? `Project · ${currentProject.title}` : 'No project linked'}</span>
            <span className={styles.metaStaticChip}>{currentArea ? `Area · ${currentArea.title}` : 'No area linked'}</span>
            <span className={styles.metaStaticChip}>{currentOwner ? `Owner · ${currentOwner.title}` : 'No owner linked'}</span>
          </div>
          {currentProject ? (
            <Link to={pathForEntity(currentProject)} className={styles.workspaceLinkCard}>
              <strong>{currentProject.title || 'Untitled project'}</strong>
              <span className={styles.mutedMeta}>Open parent project</span>
            </Link>
          ) : (
            <p className={styles.muted}>Link this task into a project or area so it stays anchored in the workspace.</p>
          )}
        </section>

        <section className={styles.workspaceCard}>
          <h3>Supporting context</h3>
          <div className={styles.workspaceCoverage}>
            <span className={styles.metaStaticChip}>{sourceNotes.length} source notes</span>
            <span className={styles.metaStaticChip}>{relatedNotes.length} related notes</span>
            <span className={styles.metaStaticChip}>{resources.length} resources</span>
            <span className={styles.metaStaticChip}>{relatedTasks.length} related tasks</span>
          </div>
          {sourceNotes[0] ? (
            <Link to={pathForEntity(sourceNotes[0].entity)} className={styles.workspaceLinkCard}>
              <strong>{sourceNotes[0].entity.title || 'Untitled note'}</strong>
              <span className={styles.mutedMeta}>Open the source note behind this task</span>
            </Link>
          ) : (
            <p className={styles.muted}>Add the source note or supporting references if this task needs more context later.</p>
          )}
        </section>

        <section className={styles.workspaceCard}>
          <h3>Watchouts</h3>
          {warnings.length > 0 ? (
            <ul className={styles.workspaceWarnings}>
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : blockedBy.length === 0 && blocks.length === 0 ? (
            <p className={styles.muted}>No obvious execution risks right now.</p>
          ) : (
            <div className={styles.workspaceCoverage}>
              {blockedBy.map((item) => (
                <span key={item.relationship.id} className={styles.metaStaticChip}>
                  Blocked by · {item.entity.title}
                </span>
              ))}
              {blocks.map((item) => (
                <span key={item.relationship.id} className={styles.metaStaticChip}>
                  Blocking · {item.entity.title}
                </span>
              ))}
            </div>
          )}
        </section>
      </div>
    </CollapsibleSection>
  );
}

function AreaWorkspacePanel({ entity, detail }) {
  const projects = sectionItems(detail, 'projects');
  const tasks = sectionItems(detail, 'tasks');
  const notes = sectionItems(detail, 'notes');
  const resources = sectionItems(detail, 'resources');
  const people = sectionItems(detail, 'people');

  const activeProjects = projects.filter((item) => item.entity.status === 'active');
  const openProjectTasks = projects.reduce((sum, item) => sum + (item.entity.task_counts?.open || 0), 0);
  const totalProjectTasks = projects.reduce((sum, item) => sum + (item.entity.task_counts?.total || 0), 0);
  const directOpenTasks = tasks.filter((item) => ['open', 'in_progress', 'waiting', 'blocked'].includes(item.entity.status));
  const leadProject = [...projects].sort((left, right) => {
    const leftOpen = left.entity.task_counts?.open || 0;
    const rightOpen = right.entity.task_counts?.open || 0;
    if (rightOpen !== leftOpen) return rightOpen - leftOpen;
    const leftTotal = left.entity.task_counts?.total || 0;
    const rightTotal = right.entity.task_counts?.total || 0;
    return rightTotal - leftTotal;
  })[0] || null;

  const warnings = [];
  if (projects.length === 0) warnings.push('No projects linked');
  if (activeProjects.length === 0 && projects.length > 0) warnings.push('No active projects');
  if (!entity.follow_up_at && !entity.due_at) warnings.push('No review date set');
  if (notes.length === 0) warnings.push('No area notes linked');
  if (people.length === 0) warnings.push('No people linked');

  return (
    <CollapsibleSection
      ariaLabel="Area workspace"
      className={`${styles.workspacePanel} ${styles.workspacePanelWarm}`}
      headerClassName={styles.workspaceHeader}
      eyebrow="Area workspace"
      title="Portfolio snapshot"
      canCollapse={false}
      meta={(
        <div className={styles.workspaceStats}>
          <div className={styles.workspaceStat}>
            <strong>{activeProjects.length}</strong>
            <span>active projects</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{openProjectTasks + directOpenTasks.length}</strong>
            <span>open work</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{notes.length}</strong>
            <span>notes</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{people.length}</strong>
            <span>people</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{resources.length}</strong>
            <span>resources</span>
          </div>
        </div>
      )}
    >
      <div className={styles.workspaceGrid}>
        <section className={styles.workspaceCard}>
          <h3>Lead project</h3>
          {leadProject ? (
            <Link to={pathForEntity(leadProject.entity)} className={styles.workspaceLinkCard}>
              <strong>{leadProject.entity.title || 'Untitled project'}</strong>
              <span className={styles.metaRow}>
                <span className={styles.statusPill}>{leadProject.entity.status}</span>
                <span className={styles.metaStaticChip}>
                  {leadProject.entity.task_counts?.open || 0} open / {leadProject.entity.task_counts?.total || 0} total tasks
                </span>
              </span>
            </Link>
          ) : (
            <p className={styles.muted}>Link a project into this area to give the portfolio a clear center of gravity.</p>
          )}
        </section>

        <section className={styles.workspaceCard}>
          <h3>Coverage</h3>
          <div className={styles.workspaceCoverage}>
            <span className={styles.metaStaticChip}>{projects.length} projects linked</span>
            <span className={styles.metaStaticChip}>{totalProjectTasks} project tasks tracked</span>
            <span className={styles.metaStaticChip}>{directOpenTasks.length} direct open tasks</span>
            <span className={styles.metaStaticChip}>{notes.length} notes linked</span>
            <span className={styles.metaStaticChip}>{people.length} people linked</span>
            <span className={styles.metaStaticChip}>{resources.length} resources linked</span>
          </div>
        </section>

        <section className={styles.workspaceCard}>
          <h3>Watchouts</h3>
          {warnings.length > 0 ? (
            <ul className={styles.workspaceWarnings}>
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>No obvious stewardship gaps right now.</p>
          )}
        </section>
      </div>
    </CollapsibleSection>
  );
}

function PersonWorkspacePanel({ entity, detail }) {
  const assignedTasks = sectionItems(detail, 'assigned_tasks');
  const notes = sectionItems(detail, 'mentioned_in_notes');
  const projects = sectionItems(detail, 'projects');
  const resources = sectionItems(detail, 'resources');
  const relatedPeople = sectionItems(detail, 'related_people');
  const currentLoad = detail?.current_load || [];

  const openAssignedTasks = assignedTasks.filter((item) => ['open', 'in_progress', 'waiting', 'blocked'].includes(item.entity.status));
  const blockedAssignedTasks = openAssignedTasks.filter((item) => ['waiting', 'blocked'].includes(item.entity.status));
  const activeProjects = projects.filter((item) => item.entity.status === 'active');

  const warnings = [];
  if (openAssignedTasks.length === 0) warnings.push('No open assigned tasks');
  if (blockedAssignedTasks.length === openAssignedTasks.length && openAssignedTasks.length > 0) warnings.push('All open assigned tasks are blocked or waiting');
  if (!entity.follow_up_at) warnings.push('No follow-up date set');
  if (notes.length === 0) warnings.push('No notes linked');

  return (
    <CollapsibleSection
      ariaLabel="Person workspace"
      className={`${styles.workspacePanel} ${styles.workspacePanelWarm}`}
      headerClassName={styles.workspaceHeader}
      eyebrow="Person workspace"
      title="Relationship snapshot"
      canCollapse={false}
      meta={(
        <div className={styles.workspaceStats}>
          <div className={styles.workspaceStat}>
            <strong>{openAssignedTasks.length}</strong>
            <span>open tasks</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{activeProjects.length}</strong>
            <span>active projects</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{notes.length}</strong>
            <span>notes</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{resources.length}</strong>
            <span>resources</span>
          </div>
        </div>
      )}
    >
      <div className={styles.workspaceGrid}>
        <section className={styles.workspaceCard}>
          <h3>Current load</h3>
          {currentLoad.length > 0 ? (
            <ul className={styles.eventList}>
              {currentLoad.map(({ task, last_heard_at: lastHeardAt, last_heard_preview: lastHeardPreview }) => (
                <li key={task.id} className={styles.eventItem}>
                  <Link to={pathForEntity(task)} className={styles.workspaceLinkCard}>
                    <strong>{task.title || 'Untitled task'}</strong>
                    <span className={styles.metaRow}>
                      <span className={styles.statusPill}>{task.status}</span>
                      {task.properties?.priority ? <span className={styles.priorityPill}>Priority {task.properties.priority}</span> : null}
                    </span>
                  </Link>
                  <p className={styles.mutedMeta}>
                    {lastHeardAt
                      ? `Last heard ${formatDateTime(lastHeardAt)}${lastHeardPreview ? ` — ${lastHeardPreview}` : ''}`
                      : 'No activity update yet'}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>No open assigned task is linked right now.</p>
          )}
        </section>

        <section className={styles.workspaceCard}>
          <h3>Coverage</h3>
          <div className={styles.workspaceCoverage}>
            <span className={styles.metaStaticChip}>{assignedTasks.length} assigned tasks</span>
            <span className={styles.metaStaticChip}>{projects.length} projects linked</span>
            <span className={styles.metaStaticChip}>{notes.length} notes linked</span>
            <span className={styles.metaStaticChip}>{resources.length} resources linked</span>
            <span className={styles.metaStaticChip}>{relatedPeople.length} related people</span>
          </div>
        </section>

        <section className={styles.workspaceCard}>
          <h3>Watchouts</h3>
          {warnings.length > 0 ? (
            <ul className={styles.workspaceWarnings}>
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>No obvious coordination gaps right now.</p>
          )}
        </section>
      </div>
    </CollapsibleSection>
  );
}

function ResourceWorkspacePanel({ entity, detail }) {
  const notes = sectionItems(detail, 'referenced_by_notes');
  const projects = sectionItems(detail, 'projects');
  const tasks = sectionItems(detail, 'tasks');
  const areas = sectionItems(detail, 'areas');
  const people = sectionItems(detail, 'people');
  const relatedResources = sectionItems(detail, 'related_resources');

  const activeProjects = projects.filter((item) => item.entity.status === 'active');
  const openTasks = tasks.filter((item) => ['open', 'in_progress', 'waiting', 'blocked'].includes(item.entity.status));
  const primaryAnchor = activeProjects[0]?.entity || openTasks[0]?.entity || areas[0]?.entity || people[0]?.entity || null;

  const warnings = [];
  if (activeProjects.length === 0 && openTasks.length === 0) warnings.push('Not linked to active project or open task');
  if (notes.length === 0) warnings.push('No reference notes linked');
  if (!entity.follow_up_at) warnings.push('No follow-up date set');
  if (people.length === 0 && projects.length === 0 && tasks.length === 0 && areas.length === 0) warnings.push('No clear workspace anchor linked');

  return (
    <CollapsibleSection
      ariaLabel="Resource workspace"
      className={`${styles.workspacePanel} ${styles.workspacePanelWarm}`}
      headerClassName={styles.workspaceHeader}
      eyebrow="Resource workspace"
      title="Adoption snapshot"
      canCollapse={false}
      meta={(
        <div className={styles.workspaceStats}>
          <div className={styles.workspaceStat}>
            <strong>{activeProjects.length}</strong>
            <span>active projects</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{openTasks.length}</strong>
            <span>open tasks</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{notes.length}</strong>
            <span>notes</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{people.length}</strong>
            <span>people</span>
          </div>
        </div>
      )}
    >
      <div className={styles.workspaceGrid}>
        <section className={styles.workspaceCard}>
          <h3>Primary anchor</h3>
          {primaryAnchor ? (
            <Link to={pathForEntity(primaryAnchor)} className={styles.workspaceLinkCard}>
              <strong>{primaryAnchor.title || 'Untitled'}</strong>
              <span className={styles.mutedMeta}>Open the main linked context for this resource</span>
            </Link>
          ) : (
            <p className={styles.muted}>Link this resource to a project, task, area, or person so it has a clear place in the workspace.</p>
          )}
        </section>

        <section className={styles.workspaceCard}>
          <h3>Coverage</h3>
          <div className={styles.workspaceCoverage}>
            <span className={styles.metaStaticChip}>{projects.length} projects linked</span>
            <span className={styles.metaStaticChip}>{tasks.length} tasks linked</span>
            <span className={styles.metaStaticChip}>{areas.length} areas linked</span>
            <span className={styles.metaStaticChip}>{people.length} people linked</span>
            <span className={styles.metaStaticChip}>{notes.length} notes linked</span>
            <span className={styles.metaStaticChip}>{relatedResources.length} related resources</span>
          </div>
        </section>

        <section className={styles.workspaceCard}>
          <h3>Watchouts</h3>
          {warnings.length > 0 ? (
            <ul className={styles.workspaceWarnings}>
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>No obvious adoption gaps right now.</p>
          )}
        </section>
      </div>
    </CollapsibleSection>
  );
}

function NoteWorkspacePanel({ entity, detail }) {
  const [pendingSuggestions, setPendingSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);

  const derivedTasks = sectionItems(detail, 'derived_tasks');
  const projects = sectionItems(detail, 'projects');
  const people = sectionItems(detail, 'people_mentioned');
  const resources = sectionItems(detail, 'referenced_resources');
  const relatedNotes = sectionItems(detail, 'related_notes');
  const extractionCount = derivedTasks.length + projects.length + people.length + resources.length;

  useEffect(() => {
    let active = true;
    setLoading(true);
    v4API.suggestions.list({ status: 'pending' })
      .then((response) => {
        if (!active) return;
        const relevant = (response.data || []).filter((suggestion) => suggestion.source_entity_id === entity.id);
        setPendingSuggestions(relevant);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setPendingSuggestions([]);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [entity.id]);

  return (
    <CollapsibleSection
      ariaLabel="Note workspace"
      className={`${styles.workspacePanel} ${styles.workspacePanelWarm}`}
      headerClassName={styles.workspaceHeader}
      eyebrow="Note workspace"
      title="Source note outcomes"
      canCollapse={false}
      meta={(
        <div className={styles.workspaceStats}>
          <div className={styles.workspaceStat}>
            <strong>{extractionCount}</strong>
            <span>linked outcomes</span>
          </div>
          <div className={styles.workspaceStat}>
            <strong>{pendingSuggestions.length}</strong>
            <span>pending review</span>
          </div>
        </div>
      )}
    >
      <div className={styles.workspaceGrid}>
        <section className={styles.workspaceCard}>
          <h3>Extraction outcomes</h3>
          <div className={styles.workspaceCoverage}>
            <span className={styles.metaStaticChip}>{derivedTasks.length} tasks</span>
            <span className={styles.metaStaticChip}>{projects.length} projects</span>
            <span className={styles.metaStaticChip}>{people.length} people</span>
            <span className={styles.metaStaticChip}>{resources.length} resources</span>
            {relatedNotes.length > 0 ? <span className={styles.metaStaticChip}>{relatedNotes.length} related notes</span> : null}
          </div>
          {extractionCount > 0 ? (
            <p className={styles.inspectionBody}>This note is already connected into the workspace. Use the segments below to inspect or extend the linked entities.</p>
          ) : (
            <p className={styles.muted}>No linked entities yet. Re-run extraction or link entities manually if this note should drive follow-up work.</p>
          )}
        </section>

        <section className={styles.workspaceCard}>
          <h3>Review state</h3>
          {loading ? (
            <p className={styles.muted}>Loading review state…</p>
          ) : pendingSuggestions.length > 0 ? (
            <>
              <p className={styles.inspectionBody}>
                {pendingSuggestions.length} suggestion{pendingSuggestions.length === 1 ? '' : 's'} from this note still {pendingSuggestions.length === 1 ? 'needs' : 'need'} review.
              </p>
              <Link to="/suggestions" className={styles.workspaceLinkCard}>
                <strong>Open Suggestions</strong>
                <span className={styles.mutedMeta}>Review pending AI suggestions for this source note.</span>
              </Link>
            </>
          ) : (
            <p className={styles.muted}>No pending suggestions from this note right now.</p>
          )}
        </section>
      </div>
    </CollapsibleSection>
  );
}

function EntityInspectionPanel({ entity, events, loading, error }) {
  const aiSummary = entity.ai?.entity_summary || entity.ai?.summary;
  const aiStatus = humanizeToken(entity.ai?.status || 'pending');
  const confidence = formatConfidence(entity.ai?.confidence);
  const recentEvents = events.filter(shouldShowEvent).slice(0, 6);

  return (
    <CollapsibleSection
      ariaLabel="Inspection and trust"
      className={`${styles.inspectionPanel} ${styles.inspectionPanelCool}`}
      headerClassName={styles.inspectionHeader}
      eyebrow="Inspection"
      title="Trust and recent changes"
      canCollapse={false}
      meta={(
        <div className={styles.metaStrip}>
          <span className={styles.metaStaticChip}>Source · {humanizeToken(entity.source || 'manual')}</span>
          <span className={styles.metaStaticChip}>AI · {aiStatus || 'pending'}</span>
          {confidence ? <span className={styles.metaStaticChip}>{confidence}</span> : null}
        </div>
      )}
    >
      <div className={styles.inspectionGrid}>
        <section className={styles.inspectionCard}>
          <h3>Signals</h3>
          <div className={styles.inspectionChips}>
            <span className={styles.metaStaticChip}>Created · {formatDateTime(entity.created_at)}</span>
            <span className={styles.metaStaticChip}>Updated · {formatDateTime(entity.updated_at)}</span>
            {entity.properties?.priority ? <span className={styles.metaStaticChip}>Priority · {entity.properties.priority}</span> : null}
          </div>
          {aiSummary ? (
            <p className={styles.inspectionBody}>{aiSummary}</p>
          ) : (
            <p className={styles.muted}>No AI summary available yet.</p>
          )}
        </section>

        <section className={styles.inspectionCard}>
          <h3>Recent history</h3>
          {loading ? (
            <p className={styles.muted}>Loading history…</p>
          ) : error ? (
            <p className={styles.muted}>{error}</p>
          ) : recentEvents.length === 0 ? (
            <p className={styles.muted}>No recorded events yet.</p>
          ) : (
            <ul className={styles.eventList}>
              {recentEvents.map((event) => (
                <li key={event.id} className={styles.eventItem}>
                  <div className={styles.eventHeader}>
                    <strong>{eventTitle(event)}</strong>
                    <span className={styles.mutedMeta}>{formatDateTime(event.created_at)}</span>
                  </div>
                  <div className={styles.inspectionChips}>
                    <span className={styles.metaStaticChip}>{humanizeToken(event.actor || 'user')}</span>
                    {event.confidence !== null && event.confidence !== undefined ? (
                      <span className={styles.metaStaticChip}>{formatConfidence(event.confidence)}</span>
                    ) : null}
                  </div>
                  {eventReason(event) ? <p className={styles.eventReason}>{eventReason(event)}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </CollapsibleSection>
  );
}

function ActivityUpdatesSection({ entityId, className = '' }) {
  const [updates, setUpdates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [draft, setDraft] = useState('');

  useEffect(() => {
    let active = true;
    v4API.activityUpdates.list(entityId)
      .then((response) => { if (active) { setUpdates(response.data || []); setLoading(false); } })
      .catch(() => { if (active) { setError('Failed to load activity updates'); setLoading(false); } });
    return () => { active = false; };
  }, [entityId]);

  async function handleSubmit(event) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      await v4API.activityUpdates.create(entityId, content);
      const response = await v4API.activityUpdates.list(entityId);
      setUpdates(response.data || []);
      setDraft('');
    } catch (err) {
      setError(err.message || 'Failed to add activity update');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <CollapsibleSection
      ariaLabel="Activity Updates"
      className={[styles.segmentPanel, styles.segmentPanelWarm, className].filter(Boolean).join(' ')}
      headerClassName={styles.segmentHeader}
      title="Activity Updates"
      canCollapse={false}
      meta={<span className={styles.countPill}>{updates.length}</span>}
    >
      <form onSubmit={handleSubmit} className={styles.activityUpdateForm}>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Add an activity update…"
          aria-label="Activity update"
          rows={2}
          disabled={submitting}
        />
        <button
          className={styles.primaryButton}
          type="submit"
          disabled={!draft.trim() || submitting}
        >
          {submitting ? 'Adding…' : 'Add update'}
        </button>
      </form>
      {error && <div className={styles.error} role="alert">{error}</div>}
      {loading ? (
        <p className={styles.muted}>Loading…</p>
      ) : updates.length === 0 ? (
        <p className={styles.muted}>No activity updates yet.</p>
      ) : (
        <ul className={styles.activityUpdatesList}>
          {updates.map((note) => (
            <li key={note.id} className={styles.activityUpdateItem}>
              <p className={styles.activityUpdateContent}>{note.content}</p>
              <span className={styles.activityUpdateMeta}>
                {formatDateTime(note.updated_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </CollapsibleSection>
  );
}

function CaptureChangesPanel({ entityId, className = '' }) {
  const [changes, setChanges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revertingId, setRevertingId] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const response = await v4API.entities.captureChanges(entityId);
      setChanges(response.data || []);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load agent changes');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    load().catch(() => {});
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityId]);

  async function handleRevert(eventId) {
    setRevertingId(eventId);
    setError('');
    try {
      await v4API.events.revert(eventId);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to revert change');
    } finally {
      setRevertingId(null);
    }
  }

  if (!loading && changes.length === 0 && !error) return null;

  return (
    <CollapsibleSection
      ariaLabel="What the agent did"
      className={[styles.segmentPanel, styles.segmentPanelCool, className].filter(Boolean).join(' ')}
      headerClassName={styles.segmentHeader}
      title="What the agent did"
      canCollapse={false}
      meta={<span className={styles.countPill}>{changes.length}</span>}
    >
      {error && <div className={styles.error} role="alert">{error}</div>}
      {loading ? (
        <p className={styles.muted}>Loading…</p>
      ) : (
        <ul className={styles.eventList}>
          {changes.map((change) => (
            <li key={change.id} className={styles.eventItem}>
              <div className={styles.eventHeader}>
                <strong>{eventTitle(change)}</strong>
                <span className={styles.mutedMeta}>{formatDateTime(change.created_at)}</span>
              </div>
              {eventReason(change) ? <p className={styles.eventReason}>{eventReason(change)}</p> : null}
              <div>
                {change.reverted_at ? (
                  <span className={styles.metaStaticChip}>Reverted</span>
                ) : (
                  <button
                    type="button"
                    className={styles.secondaryButton}
                    onClick={() => handleRevert(change.id)}
                    disabled={revertingId === change.id}
                  >
                    {revertingId === change.id ? 'Reverting…' : 'Revert'}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </CollapsibleSection>
  );
}

function RelationshipSegment({
  config,
  currentId,
  sections,
  onCreate,
  onLink,
  onRemove,
  onQuickStatus,
}) {
  const items = sections.flatMap((section) => section.items);
  const [actionOpen, setActionOpen] = useState(false);
  const canCollapse = items.length > 0;
  const [expanded, setExpanded] = useState(items.length > 0);
  const isCollapsed = canCollapse && !expanded;

  return (
    <article className={[
      styles.segmentPanel,
      styles.segmentPanelWarm,
      isCollapsed ? styles.segmentPanelCollapsed : '',
      config.size === 'narrow' ? styles.segmentPanelNarrow : styles.segmentPanelWide,
    ].filter(Boolean).join(' ')}>
      <header className={styles.segmentHeader}>
        <h2>{config.title}</h2>
        <div className={styles.segmentHeaderRight}>
          <span className={styles.countPill}>{items.length}</span>
          {canCollapse ? (
            <button
              type="button"
              className={styles.collapseButton}
              onClick={() => setExpanded((value) => !value)}
              aria-expanded={expanded}
              aria-label={`${expanded ? 'Collapse' : 'Expand'} ${config.title}`}
              title={expanded ? 'Collapse section' : 'Expand section'}
            >
              {expanded ? <ChevronDown size={14} strokeWidth={2.4} aria-hidden="true" /> : <ChevronRight size={14} strokeWidth={2.4} aria-hidden="true" />}
              <span>{expanded ? 'Collapse' : 'Expand'}</span>
            </button>
          ) : null}
          {config.type && (
            <button
              type="button"
              className={`${styles.addButton} ${styles.addButtonIcon}`}
              onClick={() => {
                setExpanded(true);
                setActionOpen((v) => !v);
              }}
              aria-expanded={actionOpen}
              aria-label={actionOpen ? `Close add ${config.type}` : `Add ${config.type}`}
              title={actionOpen ? 'Close' : `Add ${config.type}`}
            >
              {actionOpen
                ? <X size={14} strokeWidth={2.2} aria-hidden="true" />
                : <Plus size={14} strokeWidth={2.2} aria-hidden="true" />}
            </button>
          )}
        </div>
      </header>

      {config.type && actionOpen && (
        <ActionModal
          title={`Add ${config.title.toLowerCase()}`}
          onClose={() => setActionOpen(false)}
        >
          <TypedAction
            config={config}
            currentId={currentId}
            onCreate={async (form) => { await onCreate(form); setActionOpen(false); }}
            onLink={async (targetId) => { await onLink(targetId); setActionOpen(false); }}
          />
        </ActionModal>
      )}

      {expanded ? (
        <div className={styles.linkedArea}>
          {sections.length === 0 || items.length === 0 ? null : (
            sections.map((section) => (
              section.items.length > 0 && (
                <div key={section.key} className={styles.linkedGroup}>
                  {sections.length > 1 && <h3>{section.title}</h3>}
                  <ul className={styles.cards}>
                    {section.items.map((item) => (
                      <LinkedEntityRow
                        key={item.relationship.id}
                        item={item}
                        onRemove={onRemove}
                        onQuickStatus={onQuickStatus}
                        showType={!config.type}
                      />
                    ))}
                  </ul>
                </div>
              )
            ))
          )}
        </div>
      ) : null}
    </article>
  );
}

function LinkedEntityRow({ item, onRemove, onQuickStatus, showType = false }) {
  return (
    <li>
      <Link to={pathForEntity(item.entity)}>
        <strong>{item.entity.title || 'Untitled'}</strong>
        <span className={styles.metaRow}>
          {showType && <span className={styles.typePill}>{item.entity.type}</span>}
          <span className={styles.statusPill}>{item.entity.status}</span>
          <span className={styles.relationshipPill}>{item.relationship.relationship_type}</span>
        </span>
        {item.entity.due_at && <span className={styles.mutedMeta}>Due {new Date(item.entity.due_at).toLocaleString()}</span>}
        {item.entity.properties?.priority && <span className={styles.priorityPill}>Priority {item.entity.properties.priority}</span>}
      </Link>
      <div className={styles.cardActions}>
        {item.entity.type === 'task' && (
          <select
            className={styles.rowStatusSelect}
            value={item.entity.status}
            onChange={(event) => onQuickStatus(item.entity.id, event.target.value)}
            aria-label={`Set ${item.entity.title || 'task'} status`}
          >
            {statusOptions.task.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
        )}
        <button
          className={styles.removeButton}
          type="button"
          onClick={() => onRemove(item.relationship.id)}
          aria-label="Remove"
          title="Remove"
        >
          <X size={14} strokeWidth={2.4} aria-hidden="true" />
        </button>
      </div>
    </li>
  );
}

function InlineTextField({ value, onChange, onCommit, placeholder, ariaLabel, className, type = 'text', renderEmpty }) {
  const [editing, setEditing] = useState(false);
  const initialRef = React.useRef(value);
  const inputRef = React.useRef(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      initialRef.current = value;
      inputRef.current.focus();
      inputRef.current.select?.();
    }
  }, [editing, value]);

  function commit() {
    setEditing(false);
  }

  function cancel() {
    if (onChange) onChange(initialRef.current);
    setEditing(false);
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        className={`${styles.inlineInput} ${className || ''}`}
        value={value}
        type={type}
        placeholder={placeholder}
        aria-label={ariaLabel}
        onChange={(event) => onChange(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && type !== 'textarea') {
            event.preventDefault();
            commit();
          } else if (event.key === 'Escape') {
            event.preventDefault();
            cancel();
          }
        }}
      />
    );
  }

  const display = value && value.length ? value : (renderEmpty || placeholder || 'Click to edit');
  return (
    <button
      type="button"
      className={`${styles.inlineDisplay} ${className || ''} ${!value ? styles.inlineDisplayEmpty : ''}`}
      onClick={() => setEditing(true)}
      aria-label={ariaLabel}
      title="Click to edit"
    >
      {display}
    </button>
  );
}

function InlineDateField({ value, onChange, ariaLabel }) {
  const [editing, setEditing] = useState(false);
  const inputRef = React.useRef(null);

  useEffect(() => {
    if (editing && inputRef.current) inputRef.current.focus();
  }, [editing]);

  function commit() {
    setEditing(false);
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        className={styles.metaChip}
        type="datetime-local"
        value={value || ''}
        aria-label={ariaLabel}
        onChange={(event) => onChange(event.target.value)}
        onBlur={commit}
      />
    );
  }

  const display = value ? formatDateTime(value) : '—';
  return (
    <button
      type="button"
      className={`${styles.metaStaticChip} ${styles.metaStaticChipButton} ${!value ? styles.inlineDisplayEmpty : ''}`}
      onClick={() => setEditing(true)}
      aria-label={ariaLabel}
      title="Click to edit"
    >
      {display}
    </button>
  );
}

function InlineMarkdownField({ value, onChange, placeholder }) {
  const [editing, setEditing] = useState(false);
  const containerRef = React.useRef(null);

  useEffect(() => {
    if (!editing) return undefined;
    function onClick(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setEditing(false);
      }
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [editing]);

  if (editing) {
    return (
      <div ref={containerRef}>
        <MarkdownEditor
          value={value || ''}
          onChange={onChange}
          placeholder={placeholder}
          minRows={6}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      className={`${styles.inlineMarkdownDisplay} ${!value ? styles.inlineDisplayEmpty : ''}`}
      onClick={() => setEditing(true)}
      aria-label="Description"
      title="Click to edit"
    >
      {value
        ? <MarkdownContent content={value} />
        : <span>{placeholder}</span>}
    </button>
  );
}

function TagsField({ value, onChange }) {
  const list = Array.isArray(value) ? value : [];
  const [adding, setAdding] = useState(false);
  const [draftTag, setDraftTag] = useState('');
  const inputRef = React.useRef(null);

  useEffect(() => {
    if (adding && inputRef.current) inputRef.current.focus();
  }, [adding]);

  function commit() {
    const t = draftTag.trim().replace(/^#/, '').toLowerCase();
    setDraftTag('');
    setAdding(false);
    if (!t) return;
    if (list.includes(t)) return;
    onChange([...list, t]);
  }

  function removeAt(index) {
    const next = list.slice();
    next.splice(index, 1);
    onChange(next);
  }

  return (
    <div className={styles.tagChipRow}>
      {list.map((tag, index) => (
        <span key={`${tag}-${index}`} className={styles.tagChip}>
          <Link
            to={`/search?tag=${encodeURIComponent(tag)}`}
            className={styles.tagChipLink}
            title={`Find all items tagged #${tag}`}
          >
            {tag}
          </Link>
          <button
            type="button"
            className={styles.tagChipRemove}
            onClick={() => removeAt(index)}
            aria-label={`Remove tag ${tag}`}
            title="Remove"
          >
            <X size={11} strokeWidth={2.4} aria-hidden="true" />
          </button>
        </span>
      ))}
      {adding ? (
        <input
          ref={inputRef}
          className={styles.tagChipInput}
          value={draftTag}
          placeholder="tag"
          onChange={(event) => setDraftTag(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ',') {
              event.preventDefault();
              commit();
            } else if (event.key === 'Escape') {
              event.preventDefault();
              setDraftTag('');
              setAdding(false);
            } else if (event.key === 'Backspace' && !draftTag && list.length) {
              event.preventDefault();
              removeAt(list.length - 1);
            }
          }}
        />
      ) : (
        <button
          type="button"
          className={styles.tagChipAdd}
          onClick={() => setAdding(true)}
          aria-label="Add tag"
          title="Add tag"
        >
          <Plus size={12} strokeWidth={2.4} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

function ActionModal({ title, onClose, children }) {
  useEffect(() => {
    function onKey(event) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  return (
    <div
      className={styles.modalBackdrop}
      role="presentation"
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div
        className={styles.modalDialog}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h3>{title}</h3>
          <button
            type="button"
            className={`${styles.secondaryButton} ${styles.iconButton}`}
            onClick={onClose}
            aria-label="Close"
            title="Close"
          >
            <X size={14} strokeWidth={2.2} aria-hidden="true" />
          </button>
        </header>
        <div className={styles.modalBody}>{children}</div>
      </div>
    </div>
  );
}

function TypedAction({ config, currentId, onCreate, onLink }) {
  const [mode, setMode] = useState('existing');
  const [form, setForm] = useState({ title: '', content: '', due_at: '', follow_up_at: '', priority: '' });
  const [options, setOptions] = useState([]);

  useEffect(() => {
    let active = true;
    v4API.entities.list({ type: config.type, limit: 100 })
      .then((response) => {
        if (active) setOptions(response.data || []);
      })
      .catch(() => {
        if (active) setOptions([]);
      });
    return () => {
      active = false;
    };
  }, [config.type]);

  const candidateOptions = options.filter((option) => option.id !== currentId);

  const createDisabled = config.type === 'note'
    ? !form.title.trim() && !form.content.trim()
    : !form.title.trim();

  async function submitCreate(event) {
    event.preventDefault();
    if (createDisabled) return;
    await onCreate({ ...form, title: form.title.trim(), content: form.content.trim() || null });
    setForm({ title: '', content: '', due_at: '', follow_up_at: '', priority: '' });
  }

  return (
    <article className={styles.actionCard}>
      {config.primary && (
        <div className={styles.tabs} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'existing'}
            className={mode === 'existing' ? styles.activeTab : ''}
            onClick={() => setMode('existing')}
          >
            Link existing
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'create'}
            className={mode === 'create' ? styles.activeTab : ''}
            onClick={() => setMode('create')}
          >
            Create new
          </button>
        </div>
      )}

      {mode === 'create' && config.primary ? (
        <form onSubmit={submitCreate} className={styles.actionForm} aria-label={config.primary}>
          <input
            value={form.title}
            onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
            placeholder={config.type === 'note' ? 'Optional note title' : `${config.type} title`}
            aria-label={`${config.title} title`}
          />
          <button className={styles.primaryButton} type="submit" disabled={createDisabled}>{config.primary}</button>
          <details className={styles.advancedFields}>
            <summary>{config.type === 'note' ? 'Add note body' : 'Details'}</summary>
            <textarea
              value={form.content}
              onChange={(event) => setForm((current) => ({ ...current, content: event.target.value }))}
              placeholder={config.type === 'note' ? 'Write the source note' : 'Optional content'}
              aria-label={`${config.title} content`}
              rows={2}
            />
            {config.taskFields && (
              <div className={styles.advancedGrid}>
                <input
                  className={styles.dateControl}
                  value={form.due_at}
                  onChange={(event) => setForm((current) => ({ ...current, due_at: event.target.value }))}
                  aria-label={`${config.title} due date`}
                  type="datetime-local"
                />
                <select
                  className={styles.priorityControl}
                  value={form.priority}
                  onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value }))}
                  aria-label={`${config.title} priority`}
                >
                  {priorityOptions.map((priority) => (
                    <option key={priority || 'none'} value={priority}>{priority || 'No priority'}</option>
                  ))}
                </select>
              </div>
            )}
          </details>
        </form>
      ) : (
        <LinkCombobox
          config={config}
          options={candidateOptions}
          onPick={(targetId) => onLink(targetId)}
        />
      )}
    </article>
  );
}

function LinkCombobox({ config, options, onPick }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const wrapperRef = React.useRef(null);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? options.filter((o) => `${o.title || ''} ${o.content || ''}`.toLowerCase().includes(q))
    : options;
  const limited = filtered.slice(0, 50);

  useEffect(() => { setActiveIndex(0); }, [query]);

  useEffect(() => {
    function onClick(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  function onKeyDown(event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((i) => Math.min(i + 1, limited.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const choice = limited[activeIndex];
      if (choice) onPick(choice.id);
    } else if (event.key === 'Escape') {
      setOpen(false);
    }
  }

  return (
    <div className={styles.combobox} ref={wrapperRef}>
      <input
        type="text"
        value={query}
        onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder={`Search and link a ${config.type}…`}
        aria-label={`Search and link ${config.title}`}
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={`${config.key}-combobox-list`}
        role="combobox"
      />
      {open && (
        <ul
          id={`${config.key}-combobox-list`}
          role="listbox"
          className={styles.comboboxList}
        >
          {limited.length === 0 ? (
            <li className={styles.comboboxEmpty} role="presentation">
              No matching {config.type}s
            </li>
          ) : (
            limited.map((option, index) => (
              <li
                key={option.id}
                role="option"
                aria-selected={index === activeIndex}
                className={`${styles.comboboxOption} ${index === activeIndex ? styles.comboboxOptionActive : ''}`}
                onMouseDown={(event) => { event.preventDefault(); onPick(option.id); }}
                onMouseEnter={() => setActiveIndex(index)}
              >
                <span className={styles.comboboxTitle}>{option.title || 'Untitled'}</span>
                <span className={styles.comboboxMeta}>{option.status}</span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
