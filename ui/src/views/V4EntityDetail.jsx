/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import MarkdownContent from '../components/MarkdownContent';
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
    { key: 'person', sectionKeys: ['people'], title: 'People', type: 'person', relationship: 'assigned_to', direction: 'outgoing', primary: 'Add new person', existing: 'Add existing person' },
    { key: 'resource', sectionKeys: ['resources'], title: 'Resources', type: 'resource', relationship: 'references', direction: 'outgoing', primary: 'Add new resource', existing: 'Add existing resource' },
  ],
  area: [
    { key: 'project', sectionKeys: ['projects'], title: 'Projects', type: 'project', relationship: 'parent', direction: 'incoming', primary: 'Add new project', existing: 'Add existing project' },
    { key: 'task', sectionKeys: ['tasks'], title: 'Tasks', type: 'task', relationship: 'parent', direction: 'incoming', primary: 'Add new task', existing: 'Add existing task', taskFields: true },
    { key: 'note', sectionKeys: ['notes'], title: 'Notes', type: 'note', relationship: 'related', direction: 'outgoing', primary: 'Add area note', existing: 'Link existing note' },
    { key: 'resource', sectionKeys: ['resources'], title: 'Resources', type: 'resource', relationship: 'references', direction: 'outgoing', primary: 'Add new resource', existing: 'Add existing resource' },
  ],
  task: [
    { key: 'project', sectionKeys: ['project'], title: 'Project', type: 'project', relationship: 'parent', direction: 'outgoing', existing: 'Move/link to project' },
    { key: 'area', sectionKeys: ['area'], title: 'Area', type: 'area', relationship: 'parent', direction: 'outgoing', existing: 'Move/link to area' },
    { key: 'person', sectionKeys: ['people'], title: 'Assignee', type: 'person', relationship: 'assigned_to', direction: 'outgoing', primary: 'Create and assign person', existing: 'Assign existing person' },
    { key: 'note', sectionKeys: ['source_notes', 'related_notes'], title: 'Notes', type: 'note', relationship: 'derived_from', direction: 'outgoing', primary: 'Add source note', existing: 'Attach existing note' },
    { key: 'resource', sectionKeys: ['resources'], title: 'Resources', type: 'resource', relationship: 'references', direction: 'outgoing', primary: 'Add resource', existing: 'Attach existing resource' },
    { key: 'blocker', sectionKeys: ['blocking'], title: 'Blocked By', type: 'task', relationship: 'blocks', direction: 'incoming', existing: 'Add blocking task' },
  ],
  note: [
    { key: 'task', sectionKeys: ['derived_tasks'], title: 'Derived Tasks', type: 'task', relationship: 'derived_from', direction: 'incoming', primary: 'Create task from note', existing: 'Link existing task', taskFields: true },
    { key: 'project', sectionKeys: ['projects'], title: 'Projects', type: 'project', relationship: 'related', direction: 'outgoing', primary: 'Add new project', existing: 'Link existing project' },
    { key: 'area', sectionKeys: ['areas'], title: 'Areas', type: 'area', relationship: 'related', direction: 'outgoing', existing: 'Link existing area' },
    { key: 'person', sectionKeys: ['people_mentioned'], title: 'People Mentioned', type: 'person', relationship: 'mentions', direction: 'outgoing', primary: 'Add mentioned person', existing: 'Link existing person' },
    { key: 'resource', sectionKeys: ['referenced_resources'], title: 'Referenced Resources', type: 'resource', relationship: 'references', direction: 'outgoing', primary: 'Add referenced resource', existing: 'Link existing resource' },
  ],
  person: [
    { key: 'task', sectionKeys: ['assigned_tasks'], title: 'Assigned Tasks', type: 'task', relationship: 'assigned_to', direction: 'incoming', primary: 'Add assigned task', existing: 'Assign existing task', taskFields: true },
    { key: 'note', sectionKeys: ['mentioned_in_notes'], title: 'Notes', type: 'note', relationship: 'mentions', direction: 'incoming', primary: 'Add note about person', existing: 'Link existing note' },
    { key: 'project', sectionKeys: ['projects'], title: 'Projects', type: 'project', relationship: 'assigned_to', direction: 'incoming', existing: 'Add to existing project' },
    { key: 'resource', sectionKeys: ['resources'], title: 'Resources', type: 'resource', relationship: 'references', direction: 'outgoing', primary: 'Add person resource', existing: 'Link existing resource' },
  ],
  resource: [
    { key: 'note', sectionKeys: ['referenced_by_notes'], title: 'Reference Notes', type: 'note', relationship: 'references', direction: 'incoming', primary: 'Add reference note', existing: 'Link existing note' },
    { key: 'project', sectionKeys: ['projects'], title: 'Projects', type: 'project', relationship: 'references', direction: 'incoming', existing: 'Use in existing project' },
    { key: 'task', sectionKeys: ['tasks'], title: 'Tasks', type: 'task', relationship: 'references', direction: 'incoming', existing: 'Use in existing task', taskFields: true },
    { key: 'area', sectionKeys: ['areas'], title: 'Areas', type: 'area', relationship: 'references', direction: 'incoming', existing: 'Use in existing area' },
    { key: 'person', sectionKeys: ['people'], title: 'People', type: 'person', relationship: 'references', direction: 'incoming', existing: 'Link existing person' },
  ],
};

function pathForEntity(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function toInputDateTime(value) {
  if (!value) return '';
  return value.slice(0, 16);
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
  const [detail, setDetail] = useState(null);
  const [draft, setDraft] = useState({
    title: '',
    content: '',
    status: 'active',
    due_at: '',
    follow_up_at: '',
    reference_url: '',
    tags: '',
    priority: '',
  });
  const [error, setError] = useState('');

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
      tags: (response.entity.tags || []).map((tag) => tag.name).join(', '),
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
          tags: (response.entity.tags || []).map((tag) => tag.name).join(', '),
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
        tags: draft.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
      }));
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to save entity');
    }
  }

  async function handleArchive() {
    setError('');
    try {
      await v4API.entities.delete(id);
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to archive entity');
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
  const configs = actionConfigs[entity.type] || [];
  const usedSectionKeys = new Set(configs.flatMap((config) => config.sectionKeys || []));
  const additionalSections = detail.sections.filter((section) => !usedSectionKeys.has(section.key) && section.items.length > 0);
  const [editingContent, setEditingContent] = useState(false);

  return (
    <main className={styles.screen}>
      <section className={styles.headerPanel}>
        <form onSubmit={handleSave} className={styles.detailForm} aria-label="Edit entity">
          <div className={styles.headerTop}>
            <p className={styles.eyebrow}>Engram v4 {entityType}</p>
            <div className={styles.headerActions}>
              <button className={styles.dangerButton} type="button" onClick={handleArchive}>Archive</button>
              <button className={styles.primaryButton} type="submit">Save</button>
            </div>
          </div>
          <input
            className={styles.detailTitle}
            value={draft.title}
            onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
            aria-label="Title"
            placeholder="Title"
          />
          {editingContent ? (
            <textarea
              className={styles.detailContent}
              value={draft.content}
              onChange={(event) => setDraft((current) => ({ ...current, content: event.target.value }))}
              aria-label="Content"
              placeholder="Content — supports Markdown"
              rows={6}
              autoFocus
              onBlur={() => setEditingContent(false)}
            />
          ) : (
            <div
              className={styles.detailContentPreview}
              onClick={() => setEditingContent(true)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && setEditingContent(true)}
              aria-label="Edit content"
              title="Click to edit"
            >
              {draft.content
                ? <MarkdownContent content={draft.content} />
                : <span className={styles.contentPlaceholder}>Content — supports Markdown</span>}
            </div>
          )}
          <div className={styles.metaRow}>
            <label className={styles.metaLabel}>
              <span>Status</span>
              <select
                value={draft.status}
                onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value }))}
                aria-label="Status"
              >
                {(statusOptions[entity.type] || ['active']).map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </label>
            <label className={styles.metaLabel}>
              <span>Priority</span>
              <select
                value={draft.priority}
                onChange={(event) => setDraft((current) => ({ ...current, priority: event.target.value }))}
                aria-label="Priority"
              >
                {priorityOptions.map((priority) => (
                  <option key={priority || 'none'} value={priority}>{priority || 'none'}</option>
                ))}
              </select>
            </label>
            <label className={styles.metaLabel}>
              <span>Due</span>
              <input
                value={draft.due_at}
                onChange={(event) => setDraft((current) => ({ ...current, due_at: event.target.value }))}
                aria-label="Due date"
                type="datetime-local"
              />
            </label>
            <label className={styles.metaLabel}>
              <span>Follow-up</span>
              <input
                value={draft.follow_up_at}
                onChange={(event) => setDraft((current) => ({ ...current, follow_up_at: event.target.value }))}
                aria-label="Follow-up"
                type="datetime-local"
              />
            </label>
            <label className={styles.metaLabel}>
              <span>Tags</span>
              <input
                value={draft.tags}
                onChange={(event) => setDraft((current) => ({ ...current, tags: event.target.value }))}
                aria-label="Tags"
                placeholder="tag1, tag2"
              />
            </label>
            <label className={styles.metaLabelWide}>
              <span>URL</span>
              <input
                value={draft.reference_url}
                onChange={(event) => setDraft((current) => ({ ...current, reference_url: event.target.value }))}
                aria-label="Reference URL"
                placeholder="https://..."
                type="url"
              />
            </label>
          </div>
        </form>
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

  return (
    <article className={styles.segmentPanel}>
      <header className={styles.segmentHeader}>
        <div>
          <p className={styles.segmentKicker}>{config.type || 'linked'}</p>
          <h2>{config.title}</h2>
        </div>
        <div className={styles.segmentHeaderRight}>
          <span className={styles.countPill}>{items.length}</span>
          {config.type && (
            <button
              type="button"
              className={styles.addButton}
              onClick={() => setActionOpen((v) => !v)}
              aria-expanded={actionOpen}
            >
              {actionOpen ? '✕' : `+ Add`}
            </button>
          )}
        </div>
      </header>

      {config.type && actionOpen && (
        <TypedAction
          config={config}
          currentId={currentId}
          onCreate={async (form) => { await onCreate(form); setActionOpen(false); }}
          onLink={async (targetId) => { await onLink(targetId); setActionOpen(false); }}
        />
      )}

      <div className={styles.linkedArea}>
        {sections.length === 0 || items.length === 0 ? (
          <p className={styles.emptyText}>No linked {config.title.toLowerCase()} yet.</p>
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

function LinkedEntityRow({ item, onRemove, onQuickStatus }) {
  return (
    <li>
      <Link to={pathForEntity(item.entity)}>
        <strong>{item.entity.title || 'Untitled'}</strong>
        <span className={styles.metaRow}>
          <span className={styles.typePill}>{item.entity.type}</span>
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
        <button className={styles.removeButton} type="button" onClick={() => onRemove(item.relationship.id)}>
          Remove
        </button>
      </div>
    </li>
  );
}

function TypedAction({ config, currentId, onCreate, onLink }) {
  const [mode, setMode] = useState(config.primary ? 'create' : 'existing');
  const [form, setForm] = useState({ title: '', content: '', due_at: '', follow_up_at: '', priority: '' });
  const [options, setOptions] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [filter, setFilter] = useState('');

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

  const filtered = options.filter((option) => {
    if (option.id === currentId) return false;
    const text = `${option.title || ''} ${option.content || ''}`.toLowerCase();
    return text.includes(filter.toLowerCase());
  });

  const createDisabled = config.type === 'note'
    ? !form.title.trim() && !form.content.trim()
    : !form.title.trim();

  async function submitCreate(event) {
    event.preventDefault();
    if (createDisabled) return;
    await onCreate({ ...form, title: form.title.trim(), content: form.content.trim() || null });
    setForm({ title: '', content: '', due_at: '', follow_up_at: '', priority: '' });
  }

  async function submitExisting(event) {
    event.preventDefault();
    await onLink(selectedId);
    setSelectedId('');
    setFilter('');
  }

  return (
    <article className={styles.actionCard}>
      <header>
        <h3>{config.title}</h3>
        {config.primary && (
          <div className={styles.tabs}>
            <button type="button" className={mode === 'create' ? styles.activeTab : ''} onClick={() => setMode('create')}>
              New
            </button>
            <button type="button" className={mode === 'existing' ? styles.activeTab : ''} onClick={() => setMode('existing')}>
              Existing
            </button>
          </div>
        )}
      </header>

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
        <form onSubmit={submitExisting} className={styles.actionForm} aria-label={config.existing}>
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder={`Search ${config.type}s`}
            aria-label={`Search ${config.title}`}
          />
          <select
            value={selectedId}
            onChange={(event) => setSelectedId(event.target.value)}
            aria-label={`Existing ${config.title}`}
          >
            <option value="">Choose {config.type}</option>
            {filtered.map((option) => (
              <option key={option.id} value={option.id}>
                {option.title || 'Untitled'} · {option.status}
              </option>
            ))}
          </select>
          <button className={styles.secondaryButton} type="submit" disabled={!selectedId}>{config.existing}</button>
        </form>
      )}
    </article>
  );
}
