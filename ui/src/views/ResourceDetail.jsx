import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  CheckSquare,
  ExternalLink,
  FileText,
  FolderOpen,
  Sparkles,
  Tag,
  Trash2,
  User,
} from 'lucide-react';
import { connectionsAPI, resourcesAPI, deletePreviewAPI } from '../api/engram';
import useStore from '../stores/useStore';
import {
  EntityTypeIcon,
  getEntityRoute,
  getEntityTitle,
  resolveEntity,
} from '../utils/entity';
import LinkToEntity from '../components/LinkToEntity/LinkToEntity';
import { RESOURCE_TYPES, ResourceTypeIcon } from './Resources';
import DeleteConfirmModal from '../components/DeleteConfirmModal';
import styles from './ResourceDetail.module.css';
import projectStyles from './ProjectFocus.module.css';

const TABS = [
  { key: 'notes', label: 'Notes', type: 'note' },
  { key: 'tasks', label: 'Tasks', type: 'task' },
  { key: 'people', label: 'People', type: 'person' },
];

const shellStyle = {
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1fr) 224px',
  gap: '24px',
  alignItems: 'start',
};

const cardStyle = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border)',
  borderRadius: '14px',
};

const sectionCardStyle = {
  ...cardStyle,
  padding: '16px',
  display: 'grid',
  gap: '12px',
};

const sidebarStyle = {
  width: '224px',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
};

const sidebarCardStyle = {
  ...cardStyle,
  padding: '14px',
  display: 'grid',
  gap: '10px',
};

const sidebarTitleStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  margin: 0,
  fontSize: '12px',
  fontWeight: 600,
};

const chipWrapStyle = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '8px',
};

const chipStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  padding: '4px 8px',
  borderRadius: '999px',
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  color: 'var(--text-secondary)',
  fontSize: '11px',
};

const actionButtonStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  width: '100%',
  padding: '9px 10px',
  borderRadius: '10px',
  border: '1px solid var(--border)',
  background: 'var(--bg-elevated)',
  color: 'var(--text-primary)',
  fontSize: '12px',
  textAlign: 'left',
  cursor: 'pointer',
  textDecoration: 'none',
};

const itemRowStyle = {
  ...cardStyle,
  padding: '12px 14px',
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '12px',
  textDecoration: 'none',
  color: 'inherit',
};

function isoToDatetimeLocal(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function normalizeResource(resource) {
  if (!resource) return null;
  const props = resource.properties || {};
  return {
    ...resource,
    resource_type: resource.resource_type || props.resource_type || 'OTHER',
    url: resource.url || resource.reference_url || props.url || '',
    author: resource.author || props.author || '',
    published_at: resource.published_at || props.published_at || '',
    description: resource.description || resource.content || props.description || '',
    my_notes: resource.my_notes || props.my_notes || '',
    is_read: resource.is_read ?? props.is_read ?? false,
    rating: resource.rating ?? props.rating ?? null,
    area_id: resource.area_id || props.area_id || '',
    tag_names: resource.tag_names || resource.tags?.map((tag) => tag.name) || [],
  };
}

function formatDate(value, options = {}) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    ...options,
  });
}

function getInitials(name) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean).slice(0, 2);
  if (parts.length === 0) return '?';
  return parts.map((part) => part.charAt(0).toUpperCase()).join('');
}

function mapConnectedEntities(response, store) {
  const grouped = { note: [], task: [], person: [] };
  const seen = new Set();
  const links = [...(response?.outgoing || []), ...(response?.incoming || [])];

  for (const link of links) {
    const otherId = link.src_id === store.resourceId
      ? link.dst_id
      : link.dst_id === store.resourceId
        ? link.src_id
        : link.dst_id || link.src_id;
    const embedded = link.src_id === store.resourceId
      ? link.dst_entity
      : link.dst_id === store.resourceId
        ? link.src_entity
        : link.dst_entity || link.src_entity;
    const entity = resolveEntity(otherId, store) || embedded;
    if (!entity?.id || seen.has(entity.id) || !grouped[entity.type]) continue;
    seen.add(entity.id);
    grouped[entity.type].push(entity);
  }

  return grouped;
}

export default function ResourceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const {
    resources,
    notes,
    tasks,
    people,
    areas,
    updateResource,
    deleteResource,
    getDeletePreview,
    upsertResource,
  } = useStore();

  const storeResource = useMemo(
    () => normalizeResource(resources.find((entry) => entry.id === id)),
    [id, resources],
  );

  const [resource, setResource] = useState(storeResource);
  const [loading, setLoading] = useState(!storeResource);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState('notes');
  const [linked, setLinked] = useState({ note: [], task: [], person: [] });
  const [linkRefreshKey, setLinkRefreshKey] = useState(0);

  const [title, setTitle] = useState(storeResource?.title || '');
  const [resourceType, setResourceType] = useState(storeResource?.resource_type || 'OTHER');
  const [url, setUrl] = useState(storeResource?.url || '');
  const [author, setAuthor] = useState(storeResource?.author || '');
  const [publishedAt, setPublishedAt] = useState(isoToDatetimeLocal(storeResource?.published_at));
  const [description, setDescription] = useState(storeResource?.description || '');
  const [myNotes, setMyNotes] = useState(storeResource?.my_notes || '');
  const [isRead, setIsRead] = useState(!!storeResource?.is_read);
  const [rating, setRating] = useState(storeResource?.rating ?? null);
  const [areaId, setAreaId] = useState(storeResource?.area_id || '');
  const [tagNames, setTagNames] = useState(storeResource?.tag_names || []);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePreview, setDeletePreview] = useState(null);

  const applyResource = useCallback((nextResource) => {
    const normalized = normalizeResource(nextResource);
    if (!normalized) return;
    setResource(normalized);
    setTitle(normalized.title || '');
    setResourceType(normalized.resource_type || 'OTHER');
    setUrl(normalized.url || '');
    setAuthor(normalized.author || '');
    setPublishedAt(isoToDatetimeLocal(normalized.published_at));
    setDescription(normalized.description || '');
    setMyNotes(normalized.my_notes || '');
    setIsRead(!!normalized.is_read);
    setRating(normalized.rating ?? null);
    setAreaId(normalized.area_id || '');
    setTagNames(normalized.tag_names || []);
  }, []);

  const loadResource = useCallback(async () => {
    if (storeResource) {
      applyResource(storeResource);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await resourcesAPI.get(id);
      const nextResource = normalizeResource(res.data);
      upsertResource(nextResource);
      applyResource(nextResource);
    } catch (e) {
      setError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [applyResource, id, storeResource, upsertResource]);

  useEffect(() => {
    loadResource();
  }, [loadResource]);

  useEffect(() => {
    let ignore = false;

    async function loadLinks() {
      try {
        const res = await connectionsAPI.forEntity(id);
        if (ignore) return;
        setLinked(mapConnectedEntities(res, {
          notes,
          tasks,
          people,
          resources,
          areas,
          resourceId: id,
        }));
      } catch {
        if (!ignore) {
          setLinked({ note: [], task: [], person: [] });
        }
      }
    }

    loadLinks();
    return () => {
      ignore = true;
    };
  }, [id, linkRefreshKey]);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    try {
      const payload = {
        title: title.trim(),
        resource_type: resourceType,
        url: url.trim() || null,
        author: author.trim() || null,
        published_at: publishedAt.trim() ? publishedAt : null,
        description: description.trim() || null,
        my_notes: myNotes.trim() || null,
        is_read: isRead,
        rating: rating == null ? null : Number(rating),
        area_id: areaId || null,
      };
      const updated = await updateResource(id, payload);
      applyResource(updated);
    } catch {
      // store toast handles the error
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteClick = async () => {
    try {
      const preview = await getDeletePreview(id);
      setDeletePreview(preview);
      setShowDeleteModal(true);
    } catch (e) {
      store.addToast({ type: 'error', message: e.message || 'Failed to load delete preview' });
    }
  };

  const handleDeleteConfirm = async (cascadeIds) => {
    await deleteResource(id, cascadeIds);
    setShowDeleteModal(false);
    setDeletePreview(null);
    navigate('/resources');
  };

  const activeEntities = linked[TABS.find((entry) => entry.key === tab)?.type || 'note'];
  const area = areas.find((entry) => entry.id === areaId);
  const suggestedLinks = [...linked.note, ...linked.task, ...linked.person].slice(0, 4);

  if (loading) {
    return (
      <div className={styles.page}>
        <p className={styles.loading}>Loading resource…</p>
      </div>
    );
  }

  if (error || !resource) {
    return (
      <div className={styles.page}>
        <button type="button" className={styles.backBtn} onClick={() => navigate('/resources')}>
          <ArrowLeft size={14} /> All resources
        </button>
        <p className={styles.loading}>{error || 'Resource not found.'}</p>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <nav className={styles.breadcrumb} aria-label="Breadcrumb">
        <Link to="/resources">Resources</Link>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{resource.title || 'Resource'}</span>
      </nav>

      <button type="button" className={styles.backBtn} onClick={() => navigate('/resources')}>
        <ArrowLeft size={14} /> All resources
      </button>

      <div style={shellStyle}>
        <div style={{ minWidth: 0, display: 'grid', gap: '18px' }}>
          <section style={{ ...cardStyle, padding: '18px 20px' }}>
            <div className={styles.headerRow} style={{ marginBottom: 0 }}>
              <div className={styles.typeIcon}>
                <ResourceTypeIcon type={resourceType} size={22} />
              </div>
              <div className={styles.headerText} style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                  <div style={{ minWidth: 0, flex: '1 1 320px' }}>
                    <h1>{title || 'Untitled'}</h1>
                    <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '12.5px', lineHeight: 1.5 }}>
                      {description || 'No description yet.'}
                    </p>
                    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '10px' }}>
                      <span style={chipStyle}>{resourceType}</span>
                      {author && <span style={chipStyle}>{author}</span>}
                      {publishedAt && <span style={chipStyle}>Published {formatDate(publishedAt)}</span>}
                      <span style={chipStyle}>{isRead ? 'Read' : 'Unread'}</span>
                    </div>
                    {areaId && (
                      <Link to={`/areas/${areaId}`} className={styles.areaLink}>
                        <FolderOpen size={14} />
                        {area?.title || 'Area'}
                      </Link>
                    )}
                  </div>
                  {url && (
                    <a href={url} target="_blank" rel="noreferrer" style={actionButtonStyle}>
                      <ExternalLink size={13} /> Open source
                    </a>
                  )}
                </div>
              </div>
            </div>
          </section>

          <section style={sectionCardStyle}>
            <div className={projectStyles.tabs} style={{ marginBottom: 0 }}>
              {TABS.map((entry) => (
                <button
                  key={entry.key}
                  type="button"
                  className={`${projectStyles.tab} ${tab === entry.key ? projectStyles.tabActive : ''}`}
                  onClick={() => setTab(entry.key)}
                >
                  {entry.label} ({linked[entry.type].length})
                </button>
              ))}
            </div>

            {activeEntities.length === 0 ? (
              <p className={projectStyles.empty}>No linked {tab} yet.</p>
            ) : (
              <div style={{ display: 'grid', gap: '10px' }}>
                {activeEntities.map((entity) => {
                  const route = getEntityRoute(entity);
                  const content = (
                    <>
                      <div style={{ minWidth: 0, display: 'grid', gap: '4px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                          <EntityTypeIcon type={entity.type} size={13} />
                          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                            {getEntityTitle(entity)}
                          </span>
                        </div>
                        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                          {entity.type === 'note' && (entity.project_id ? 'Linked note' : 'Standalone note')}
                          {entity.type === 'task' && (entity.status || 'Pending')}
                          {entity.type === 'person' && (entity.role || entity.email || 'No role set')}
                        </span>
                      </div>
                      <span style={chipStyle}>
                        {entity.type === 'person' ? getInitials(entity.title) : entity.type}
                      </span>
                    </>
                  );

                  if (!route) {
                    return (
                      <div key={entity.id} style={itemRowStyle}>
                        {content}
                      </div>
                    );
                  }

                  return (
                    <Link key={entity.id} to={route} style={itemRowStyle}>
                      {content}
                    </Link>
                  );
                })}
              </div>
            )}
          </section>

          <section style={sectionCardStyle}>
            <LinkToEntity entityId={id} entityType="resource" onLinkCreated={() => setLinkRefreshKey(k => k + 1)} />
          </section>

          <form className={styles.form} onSubmit={handleSave}>
            <h2>Edit</h2>

            <div>
              <label className={styles.label} htmlFor="res-title">Title</label>
              <input
                id="res-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className={styles.formRow}>
              <div>
                <label className={styles.label} htmlFor="res-type">Type</label>
                <select
                  id="res-type"
                  value={resourceType}
                  onChange={(e) => setResourceType(e.target.value)}
                >
                  {RESOURCE_TYPES.map((entry) => (
                    <option key={entry} value={entry}>{entry}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={styles.label} htmlFor="res-area">Area</label>
                <select
                  id="res-area"
                  value={areaId}
                  onChange={(e) => setAreaId(e.target.value)}
                >
                  <option value="">— None —</option>
                  {areas.map((entry) => (
                    <option key={entry.id} value={entry.id}>{entry.title}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className={styles.label} htmlFor="res-url">URL</label>
              <input id="res-url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
            </div>

            <div className={styles.formRow}>
              <div>
                <label className={styles.label} htmlFor="res-author">Author</label>
                <input id="res-author" value={author} onChange={(e) => setAuthor(e.target.value)} />
              </div>
              <div>
                <label className={styles.label} htmlFor="res-published">Published</label>
                <input
                  id="res-published"
                  type="datetime-local"
                  value={publishedAt}
                  onChange={(e) => setPublishedAt(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className={styles.label} htmlFor="res-desc">Description</label>
              <textarea id="res-desc" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>

            <div>
              <label className={styles.label} htmlFor="res-notes">My notes</label>
              <textarea id="res-notes" rows={5} value={myNotes} onChange={(e) => setMyNotes(e.target.value)} />
            </div>

            <div className={styles.formRow}>
              <div>
                <label className={styles.label} htmlFor="res-read">
                  <input
                    id="res-read"
                    type="checkbox"
                    checked={isRead}
                    onChange={(e) => setIsRead(e.target.checked)}
                  />
                  {' '}Marked as read
                </label>
              </div>
              <div>
                <label className={styles.label} htmlFor="res-rating">Rating</label>
                <input
                  id="res-rating"
                  type="number"
                  min="1"
                  max="5"
                  value={rating ?? ''}
                  onChange={(e) => setRating(e.target.value ? Number(e.target.value) : null)}
                />
              </div>
            </div>

            <div className={styles.formActions}>
              <button type="submit" className="btn btn-primary" disabled={saving || !title.trim()}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
              <button type="button" className="btn btn-ghost" onClick={handleDeleteClick}>
                <Trash2 size={14} /> Delete
              </button>
            </div>
          </form>
        </div>

        <aside style={sidebarStyle}>
          <section style={sidebarCardStyle}>
            <h2 style={sidebarTitleStyle}>
              <Tag size={13} /> Tags
            </h2>
            {tagNames.length > 0 ? (
              <div style={chipWrapStyle}>
                {tagNames.map((entry) => (
                  <span key={entry} style={chipStyle}>{entry}</span>
                ))}
              </div>
            ) : (
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '11px' }}>No tags yet.</p>
            )}
          </section>

          <section style={sidebarCardStyle}>
            <h2 style={sidebarTitleStyle}>
              <Sparkles size={13} /> Suggested links
            </h2>
            {suggestedLinks.length > 0 ? (
              suggestedLinks.map((entity) => {
                const route = getEntityRoute(entity);
                if (!route) return null;
                return (
                  <Link key={entity.id} to={route} style={{ color: 'var(--text-secondary)', textDecoration: 'none', fontSize: '12px', lineHeight: 1.4 }}>
                    {getEntityTitle(entity)}
                  </Link>
                );
              })
            ) : (
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '11px' }}>No suggested links yet.</p>
            )}
          </section>

          <section style={sidebarCardStyle}>
            <h2 style={sidebarTitleStyle}>
              <User size={13} /> Quick actions
            </h2>
            {url && (
              <a href={url} target="_blank" rel="noreferrer" style={actionButtonStyle}>
                <ExternalLink size={13} /> Open source material
              </a>
            )}
            <button
              type="button"
              style={actionButtonStyle}
              onClick={() => {
                const target = linked.note[0];
                navigate(target ? `/notes/${target.id}` : '/notes');
              }}
            >
              <FileText size={13} /> Jump to linked note
            </button>
            <button
              type="button"
              style={actionButtonStyle}
              onClick={() => {
                const target = linked.task[0];
                navigate(target ? `/tasks/${target.id}` : '/tasks');
              }}
            >
              <CheckSquare size={13} /> Open related task
            </button>
          </section>
        </aside>
      </div>

      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onClose={() => { setShowDeleteModal(false); setDeletePreview(null); }}
        onConfirm={handleDeleteConfirm}
        entityTitle={resource?.title || 'Resource'}
        entityType="resource"
        preview={deletePreview}
      />
    </div>
  );
}
