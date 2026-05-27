/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Archive, Plus, RefreshCw, Save, Trash2, X } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
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
    { key: 'person', sectionKeys: ['people'], title: 'Assignee', type: 'person', relationship: 'assigned_to', direction: 'outgoing', primary: 'Create and assign person', existing: 'Assign existing person', size: 'narrow' },
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

function cleanPayload(payload) {
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== '' && value !== undefined));
}

function relationshipPayload(currentId, linkedId, config) {
  if (config.direction === 'incoming') {
    return { sourceId: linkedId, target_entity_id: currentId, relationship_type: config.relationship };
  }
  return { sourceId: currentId, target_entity_id: linkedId, relationship_type: config.relationship };
}

export default function V4EntityDetail({ type: routeType }) {
  const { id } = useParams();
  const navigate = useNavigate();
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
  const [editingContent, setEditingContent] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessStatus, setReprocessStatus] = useState('');

  async function loadDetail() {
    const response = await v4API.entities.detail(id);
    setDetail(response);
    setDraft({
      title: response.entity.title || '',
      content: response.entity.content || '',
      status: response.entity.status || 'active',
      due_at: toInputDateTime(response.entity.due_at),
      follow_up_at: toInputDateTime(response.entity.follow_up_at),
      reference_url: response.entity.reference_url || '',
      tags: (response.entity.tags || []).map((tag) => tag.name),
      priority: response.entity.properties?.priority || '',
    });
  }

  useEffect(() => {
    let active = true;
    v4API.entities.detail(id)
      .then((response) => {
        if (!active) return;
        setDetail(response);
        setDraft({
          title: response.entity.title || '',
          content: response.entity.content || '',
          status: response.entity.status || 'active',
          due_at: toInputDateTime(response.entity.due_at),
          follow_up_at: toInputDateTime(response.entity.follow_up_at),
          reference_url: response.entity.reference_url || '',
          tags: (response.entity.tags || []).map((tag) => tag.name),
          priority: response.entity.properties?.priority || '',
        });
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [id]);

  async function commitField(partial) {
    if (!detail) return;
    try {
      await v4API.entities.update(id, cleanPayload(partial));
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to save change');
    }
  }

  async function handleSave(event) {
    event.preventDefault();
    setError('');
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
    } catch (err) {
      setError(err.message || 'Failed to save entity');
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
      navigate(collectionPathForType(entity.type));
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
  const showDueDate = entity.type !== 'note';
  const configs = actionConfigs[entity.type] || [];
  const usedSectionKeys = new Set(configs.flatMap((config) => config.sectionKeys || []));
  const additionalSections = detail.sections.filter((section) => !usedSectionKeys.has(section.key) && section.items.length > 0);

  return (
    <main className={styles.screen}>
      <section className={styles.headerPanel}>
        <form onSubmit={handleSave} className={styles.detailForm} aria-label="Edit entity">
          <div className={styles.headerTop}>
            <p className={styles.eyebrow}>Engram v4 {entityType}</p>
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
              >
                <Save size={16} strokeWidth={2} aria-hidden="true" />
              </button>
            </div>
          </div>
          <div className={styles.statusPriorityRow}>
            <div className={`${styles.pillSelect} ${styles[`statusDot_${draft.status}`] || ''}`}>
              <span className={styles.statusDot} aria-hidden="true" />
              <select
                value={draft.status}
                onChange={(event) => {
                  const next = event.target.value;
                  setDraft((current) => ({ ...current, status: next }));
                  commitField({ status: next });
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
                  const properties = { ...(detail.entity.properties || {}) };
                  if (next) properties.priority = next;
                  else delete properties.priority;
                  commitField({ properties });
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
            onChange={(val) => setDraft((current) => ({ ...current, title: val }))}
            onCommit={(val) => { if (val !== (entity.title || '')) commitField({ title: val }); }}
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
            onChange={(val) => setDraft((current) => ({ ...current, content: val }))}
            onCommit={(val) => { if (val !== (entity.content || '')) commitField({ content: val }); }}
            placeholder="Add a description — supports Markdown"
          />
          <footer className={styles.detailFooter}>
            <div className={styles.footerSection}>
              <span className={styles.footerLabel}>Tags</span>
              <TagsField
                value={draft.tags}
                onChange={(val) => {
                  setDraft((current) => ({ ...current, tags: val }));
                  commitField({ tags: val });
                }}
              />
            </div>
            <div className={styles.footerSection}>
              <span className={styles.footerLabel}>URL</span>
              <InlineTextField
                value={draft.reference_url}
                onChange={(val) => setDraft((current) => ({ ...current, reference_url: val }))}
                onCommit={(val) => { if (val !== (entity.reference_url || '')) commitField({ reference_url: val }); }}
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
                    onChange={(val) => setDraft((current) => ({ ...current, due_at: val }))}
                    onCommit={(val) => { if (val !== toInputDateTime(entity.due_at)) commitField({ due_at: val || null }); }}
                    ariaLabel="Due date"
                  />
                </div>
              )}
              <div className={styles.footerDate}>
                <span className={styles.footerLabel}>Follow-up</span>
                <InlineDateField
                  value={draft.follow_up_at}
                  onChange={(val) => setDraft((current) => ({ ...current, follow_up_at: val }))}
                  onCommit={(val) => { if (val !== toInputDateTime(entity.follow_up_at)) commitField({ follow_up_at: val || null }); }}
                  ariaLabel="Follow-up date"
                />
              </div>
              <div className={styles.footerDate}>
                <span className={styles.footerLabel}>Created</span>
                <span className={styles.metaStaticChip}>{formatDateTime(entity.created_at)}</span>
              </div>
              <div className={styles.footerDate}>
                <span className={styles.footerLabel}>Updated</span>
                <span className={styles.metaStaticChip}>{formatDateTime(entity.updated_at)}</span>
              </div>
            </div>
          </footer>
        </form>
        {reprocessStatus && (
          <div className={styles.statusBanner} role="status" aria-live="polite">
            {reprocessing && <RefreshCw size={14} strokeWidth={2} className="spin" aria-hidden="true" />}
            <span>{reprocessStatus}</span>
          </div>
        )}
        {error && <div className={styles.error}>{error}</div>}
      </section>

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
      </section>
    </main>
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
  const isCollapsed = items.length === 0 && !actionOpen;

  return (
    <article className={[
      styles.segmentPanel,
      isCollapsed ? styles.segmentPanelCollapsed : '',
      config.size === 'narrow' ? styles.segmentPanelNarrow : styles.segmentPanelWide,
    ].filter(Boolean).join(' ')}>
      <header className={styles.segmentHeader}>
        <h2>{config.title}</h2>
        <div className={styles.segmentHeaderRight}>
          <span className={styles.countPill}>{items.length}</span>
          {config.type && (
            <button
              type="button"
              className={`${styles.addButton} ${styles.addButtonIcon}`}
              onClick={() => setActionOpen((v) => !v)}
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

      <div className={styles.linkedArea}>
        {sections.length === 0 || items.length === 0 ? (
          actionOpen ? null : null
        ) : (
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
  }, [editing]);

  function commit() {
    setEditing(false);
    if (onCommit) onCommit(value);
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

function InlineDateField({ value, onChange, onCommit, ariaLabel }) {
  const [editing, setEditing] = useState(false);
  const inputRef = React.useRef(null);

  useEffect(() => {
    if (editing && inputRef.current) inputRef.current.focus();
  }, [editing]);

  function commit() {
    setEditing(false);
    if (onCommit) onCommit(value);
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

function InlineMarkdownField({ value, onChange, onCommit, placeholder }) {
  const [editing, setEditing] = useState(false);
  const containerRef = React.useRef(null);
  const lastValueRef = React.useRef(value);

  useEffect(() => { lastValueRef.current = value; }, [value]);

  useEffect(() => {
    if (!editing) return undefined;
    function onClick(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setEditing(false);
        if (onCommit) onCommit(lastValueRef.current);
      }
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [editing, onCommit]);

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
