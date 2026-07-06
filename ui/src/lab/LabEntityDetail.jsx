import {
  useCallback, useEffect, useMemo, useRef, useState,
} from 'react';
import {
  Link, useNavigate, useParams,
} from 'react-router-dom';
import { ArrowLeft, Plus } from 'lucide-react';
import { v4API, friendlyApiError } from '../api/v4Client';
import { normalizeSearchResults } from '../utils/searchResults';
import EntityGlyphCircle from '../components/EntityGlyphCircle';
import EntityDeleteButton from '../components/EntityDeleteButton';
import InlineTitleEditor from '../components/InlineTitleEditor';
import { entityTitleLabel } from '../utils/entityDisplay';
import { labDetailPath } from './labPaths';
import styles from './LabEntityDetail.module.css';

const STATUS_OPTIONS = {
  note: ['active', 'processed', 'archived'],
  task: ['open', 'in_progress', 'waiting', 'blocked', 'done', 'cancelled'],
  project: ['active', 'on_hold', 'completed', 'cancelled'],
  area: ['active', 'archived'],
  person: ['active', 'archived'],
  resource: ['active', 'archived'],
};

const PRIORITY_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
];

function toLocalInput(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (number) => String(number).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function toIsoOrNull(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function listPath(type) {
  return `/lab/${type === 'person' ? 'people' : `${type}s`}`;
}

function entityTypeFromRouteType(routeType) {
  if (routeType === 'people') return 'person';
  if (routeType === 'notes') return 'note';
  if (routeType === 'tasks') return 'task';
  if (routeType === 'projects') return 'project';
  if (routeType === 'areas') return 'area';
  if (routeType === 'resources') return 'resource';
  return routeType;
}

function buildDraft(entity) {
  return {
    status: entity?.status || '',
    due_at: toLocalInput(entity?.due_at),
    follow_up_at: toLocalInput(entity?.follow_up_at),
    priority: entity?.properties?.priority || '',
  };
}

function buildUpdatePayload(entity, draft) {
  const baseline = buildDraft(entity);
  const payload = {};
  if (draft.status !== baseline.status) {
    payload.status = draft.status || entity?.status;
  }
  if (draft.due_at !== baseline.due_at) {
    payload.due_at = toIsoOrNull(draft.due_at);
  }
  if (draft.follow_up_at !== baseline.follow_up_at) {
    payload.follow_up_at = toIsoOrNull(draft.follow_up_at);
  }
  if (draft.priority !== baseline.priority) {
    const properties = { ...(entity?.properties || {}) };
    if (draft.priority) {
      properties.priority = draft.priority;
    } else {
      delete properties.priority;
    }
    payload.properties = properties;
  }
  return payload;
}

function isDraftDirty(entity, draft) {
  const baseline = buildDraft(entity);
  return Object.keys(baseline).some((key) => baseline[key] !== draft[key]);
}

const SECTION_META = {
  project: { relationshipType: 'parent', direction: 'outgoing' },
  area: { relationshipType: 'parent', direction: 'outgoing' },
  people: { relationshipType: 'assigned_to', direction: 'outgoing' },
  people_mentioned: { relationshipType: 'mentions', direction: 'outgoing' },
  source_notes: { relationshipType: 'derived_from', direction: 'outgoing' },
  related_notes: { relationshipType: 'related', direction: 'both' },
  resources: { relationshipType: 'references', direction: 'outgoing' },
  blocking: { relationshipType: 'blocks', direction: 'both' },
  related_tasks: { relationshipType: 'related', direction: 'both' },
  update_on: { relationshipType: 'activity_update', direction: 'outgoing' },
  projects: { relationshipType: 'mentions', direction: 'outgoing' },
  areas: { relationshipType: 'mentions', direction: 'outgoing' },
  derived_tasks: { relationshipType: 'derived_from', direction: 'incoming' },
  referenced_resources: { relationshipType: 'references', direction: 'outgoing' },
  referenced_by_notes: { relationshipType: 'references', direction: 'incoming' },
  open_tasks: { relationshipType: 'parent', direction: 'incoming' },
  completed_tasks: { relationshipType: 'parent', direction: 'incoming' },
  notes: { relationshipType: 'related', direction: 'both' },
  assigned_tasks: { relationshipType: 'assigned_to', direction: 'incoming' },
  mentioned_in_notes: { relationshipType: 'mentions', direction: 'incoming' },
  related_projects: { relationshipType: 'related', direction: 'both' },
  blocked_by_blocks: { relationshipType: 'blocks', direction: 'both' },
  tasks: { relationshipType: 'parent', direction: 'incoming' },
  related_people: { relationshipType: 'related', direction: 'both' },
  related_resources: { relationshipType: 'related', direction: 'both' },
};

function sectionMeta(section) {
  return SECTION_META[section.key] || { relationshipType: 'related', direction: 'outgoing' };
}

function sectionAddRelationshipType(section) {
  return sectionMeta(section).relationshipType;
}

function canAddToSection(section) {
  if (section.key === 'activity_updates') return false;
  const { direction } = sectionMeta(section);
  return direction === 'outgoing' || direction === 'both';
}

function canCreateChildTask(section, entityType) {
  if (entityType === 'project' && section.key === 'open_tasks') return true;
  if (entityType === 'area' && section.key === 'tasks') return true;
  return false;
}

function RelationshipChip({ item }) {
  const entity = item.entity;
  const path = labDetailPath(entity);
  return (
    <span className={styles.chip}>
      {path ? <Link to={path}>{entityTitleLabel(entity, { includeType: false })}</Link> : entityTitleLabel(entity, { includeType: false })}
    </span>
  );
}

function ActivityUpdateItem({ item }) {
  return (
    <div className={styles.activityItem}>
      <span className={styles.activityTitle}>{item.title || 'Update'}</span>
      {item.content ? <p className={styles.activityContent}>{item.content}</p> : null}
    </div>
  );
}

function AddChildTaskControl({ parentEntity, onAdded }) {
  const [title, setTitle] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmed = title.trim();
    if (!trimmed || saving) return;

    setSaving(true);
    setError('');
    try {
      const created = await v4API.entities.create({
        type: 'task',
        title: trimmed,
        status: 'open',
      });
      const taskId = created?.data?.id;
      if (!taskId) {
        throw new Error('Task was not created');
      }
      await v4API.entities.createLink(taskId, {
        target_id: parentEntity.id,
        relationship_type: 'parent',
      });
      setTitle('');
      onAdded();
    } catch (err) {
      setError(friendlyApiError(err, 'Failed to add task'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className={styles.addTaskForm} onSubmit={handleSubmit}>
      <input
        type="text"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="New task title…"
        aria-label="New task title"
        disabled={saving}
        className={styles.addTaskInput}
      />
      <button
        type="submit"
        className={styles.addTaskButton}
        disabled={saving || !title.trim()}
      >
        {saving ? 'Adding…' : 'Add task'}
      </button>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
    </form>
  );
}

function SectionActions({ section, entity, onAdded }) {
  if (canCreateChildTask(section, entity.type)) {
    return <AddChildTaskControl parentEntity={entity} onAdded={onAdded} />;
  }
  if (canAddToSection(section)) {
    return (
      <AddRelationshipPicker
        entityId={entity.id}
        relationshipType={sectionAddRelationshipType(section)}
        onAdded={onAdded}
      />
    );
  }
  return null;
}

function AddRelationshipPicker({ entityId, relationshipType, onAdded }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const activeIdxRef = useRef(-1);

  useEffect(() => {
    if (!open) {
      setQuery('');
      setResults([]);
      activeIdxRef.current = -1;
      setError('');
      return undefined;
    }
    inputRef.current?.focus();
    return undefined;
  }, [open]);

  useEffect(() => {
    if (!open || query.length < 2) {
      setResults([]);
      activeIdxRef.current = -1;
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    v4API.search({ q: query, limit: 10 }).then((resp) => {
      if (cancelled) return;
      setResults(normalizeSearchResults(resp));
      setLoading(false);
    }).catch((err) => {
      if (!cancelled) {
        setError(friendlyApiError(err, 'Search failed'));
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [query, open]);

  useEffect(() => {
    if (activeIdxRef.current >= 0 && listRef.current) {
      const item = listRef.current.children[activeIdxRef.current];
      if (item) item.scrollIntoView({ block: 'nearest' });
    }
  }, [results]);

  const flatResults = useMemo(() => results, [results]);

  const handleSelect = useCallback(async (targetEntity) => {
    if (saving) return;
    setSaving(true);
    setError('');
    try {
      await v4API.entities.createLink(entityId, {
        target_id: targetEntity.id,
        relationship_type: relationshipType,
      });
      setOpen(false);
      setQuery('');
      onAdded();
    } catch (err) {
      setError(friendlyApiError(err, 'Failed to add relationship'));
    } finally {
      setSaving(false);
    }
  }, [entityId, relationshipType, saving, onAdded]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      setOpen(false);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIdxRef.current = Math.min(activeIdxRef.current + 1, flatResults.length - 1);
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIdxRef.current = Math.max(activeIdxRef.current - 1, 0);
      return;
    }
    if (e.key === 'Enter' && activeIdxRef.current >= 0) {
      e.preventDefault();
      handleSelect(flatResults[activeIdxRef.current]);
    }
  }, [flatResults, handleSelect]);

  if (!open) {
    return (
      <button
        type="button"
        className={styles.addButton}
        onClick={() => setOpen(true)}
        disabled={saving}
        aria-label="Add relationship"
      >
        <Plus size={12} strokeWidth={2} aria-hidden="true" />
        Add
      </button>
    );
  }

  return (
    <div className={styles.picker}>
      <input
        ref={inputRef}
        className={styles.pickerInput}
        type="text"
        placeholder="Search entities…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        disabled={saving}
        aria-label="Search for an entity to link"
      />
      {query.length >= 2 && (
        <div className={styles.pickerDropdown} ref={listRef}>
          {loading ? (
            <div className={styles.pickerStatus}>Searching…</div>
          ) : flatResults.length === 0 ? (
            <div className={styles.pickerStatus}>No results</div>
          ) : (
            flatResults.map((entity, idx) => (
              <div
                key={entity.id}
                className={`${styles.pickerItem} ${idx === activeIdxRef.current ? styles.pickerItemActive : ''}`}
                onMouseDown={() => handleSelect(entity)}
                onMouseEnter={() => { activeIdxRef.current = idx; }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && handleSelect(entity)}
              >
                <EntityGlyphCircle type={entity.type} />
                <span>{entityTitleLabel(entity, { includeType: false })}</span>
              </div>
            ))
          )}
        </div>
      )}
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
    </div>
  );
}

export default function LabEntityDetail() {
  const { type: routeType, id } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState(buildDraft(null));
  const [saving, setSaving] = useState(false);
  const activeIdRef = useRef(id);

  useEffect(() => {
    activeIdRef.current = id;
  }, [id]);

  const loadDetail = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await v4API.entities.detail(id);
      if (activeIdRef.current !== id) return;
      const entityType = response?.entity?.type;
      if (routeType && entityType && entityType !== entityTypeFromRouteType(routeType)) {
        navigate(labDetailPath(response.entity), { replace: true });
        return;
      }
      setDetail(response);
      setDraft(buildDraft(response?.entity));
    } catch (err) {
      if (activeIdRef.current === id) {
        setError(friendlyApiError(err, 'Failed to load entity'));
      }
    } finally {
      if (activeIdRef.current === id) {
        setLoading(false);
      }
    }
  }, [id, routeType, navigate]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const handleChange = useCallback((field, value) => {
    setDraft((current) => ({ ...current, [field]: value }));
  }, []);

  const handleSave = useCallback(async () => {
    if (!detail?.entity || !isDraftDirty(detail.entity, draft)) return;
    setSaving(true);
    setError('');
    try {
      await v4API.entities.update(id, buildUpdatePayload(detail.entity, draft));
      await loadDetail();
    } catch (err) {
      setError(friendlyApiError(err, 'Failed to save changes'));
    } finally {
      setSaving(false);
    }
  }, [detail, draft, id, loadDetail]);

  const handleCancel = useCallback(() => {
    setDraft(buildDraft(detail?.entity));
    setError('');
  }, [detail]);

  const handleTitleSave = useCallback(async (newTitle) => {
    if (!detail?.entity) return;
    setError('');
    try {
      await v4API.entities.update(id, { title: newTitle });
      await loadDetail();
    } catch (err) {
      setError(friendlyApiError(err, 'Failed to save title'));
      throw err;
    }
  }, [detail, id, loadDetail]);

  const dirty = useMemo(() => isDraftDirty(detail?.entity, draft), [detail, draft]);

  if (loading) {
    return (
      <div className={styles.page} aria-busy="true">
        <p className={styles.statusMessage}>Loading entity…</p>
      </div>
    );
  }

  if (error || !detail?.entity) {
    return (
      <div className={styles.page}>
        <p className={styles.error} role="alert">{error || 'Entity not found'}</p>
        <Link to={routeType ? listPath(routeType) : '/lab'} className={styles.backLink}>← Back</Link>
      </div>
    );
  }

  const entity = detail.entity;
  const sections = detail.sections || [];
  const statuses = STATUS_OPTIONS[entity.type] || ['active'];

  return (
    <div className={styles.page} aria-label={`${entity.type} detail`}>
      <Link to={listPath(entity.type)} className={styles.backLink}>
        <ArrowLeft size={14} strokeWidth={2} aria-hidden="true" />
        Back to {entity.type === 'person' ? 'people' : `${entity.type}s`}
      </Link>

      <header className={styles.header}>
        <div className={styles.headerTop}>
          <div className={styles.typeMeta}>
            <EntityGlyphCircle type={entity.type} />
            <span>{entity.type}</span>
          </div>
          {entity.type === 'resource' ? (
            <EntityDeleteButton
              entity={entity}
              disabled={saving}
              onDeleted={() => navigate(listPath(entity.type))}
              onError={setError}
            />
          ) : null}
        </div>
        <InlineTitleEditor
          title={entity.title || ''}
          onSave={handleTitleSave}
          className={styles.title}
          saving={saving}
        />
      </header>

      <div className={styles.editor}>
        <div className={styles.field}>
          <label htmlFor="status">Status</label>
          <select
            id="status"
            value={draft.status}
            onChange={(e) => handleChange('status', e.target.value)}
          >
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label htmlFor="priority">Priority</label>
          <select
            id="priority"
            value={draft.priority}
            onChange={(e) => handleChange('priority', e.target.value)}
          >
            {PRIORITY_OPTIONS.map((option) => (
              <option key={option.value || 'none'} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label htmlFor="due_at">Due at</label>
          <input
            id="due_at"
            type="datetime-local"
            value={draft.due_at}
            onChange={(e) => handleChange('due_at', e.target.value)}
          />
        </div>

        <div className={styles.field}>
          <label htmlFor="follow_up_at">Follow up at</label>
          <input
            id="follow_up_at"
            type="datetime-local"
            value={draft.follow_up_at}
            onChange={(e) => handleChange('follow_up_at', e.target.value)}
          />
        </div>

        {dirty ? (
          <div className={styles.actions}>
            <button type="button" className={styles.button} onClick={handleCancel} disabled={saving}>
              Cancel
            </button>
            <button type="button" className={styles.buttonPrimary} onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        ) : null}
      </div>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      {sections.map((section) => (
        <section key={section.key} className={styles.section}>
          <h2 className={styles.sectionTitle}>{section.title || section.key}</h2>
          {section.items?.length ? (
            section.key === 'activity_updates' ? (
              <div className={styles.activityList}>
                {section.items.map((item) => (
                  <ActivityUpdateItem key={item.id} item={item} />
                ))}
              </div>
            ) : (
            <div className={styles.chips}>
              {section.items.map((item) => (
                <RelationshipChip key={item.entity.id} item={item} />
              ))}
              <SectionActions section={section} entity={entity} onAdded={loadDetail} />
            </div>
            )
          ) : (
            <div className={styles.chips}>
              {canCreateChildTask(section, entity.type) || canAddToSection(section) ? (
                <SectionActions section={section} entity={entity} onAdded={loadDetail} />
              ) : (
                <p className={styles.emptyHint}>No {section.title.toLowerCase()} yet.</p>
              )}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
