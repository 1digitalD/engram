import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, MapPin, Star, Trash2 } from 'lucide-react';
import { resourcesAPI } from '../api/engram';
import useStore from '../stores/useStore';
import { RESOURCE_TYPES, ResourceTypeIcon } from './Resources';
import styles from './ResourceDetail.module.css';

function isoToDatetimeLocal(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function ResourceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { areas, updateResource, deleteResource, upsertResource } = useStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const [title, setTitle] = useState('');
  const [resourceType, setResourceType] = useState('OTHER');
  const [url, setUrl] = useState('');
  const [author, setAuthor] = useState('');
  const [publishedAt, setPublishedAt] = useState('');
  const [description, setDescription] = useState('');
  const [myNotes, setMyNotes] = useState('');
  const [isRead, setIsRead] = useState(false);
  const [rating, setRating] = useState(null);
  const [areaId, setAreaId] = useState('');
  const [tags, setTags] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await resourcesAPI.get(id);
      const r = res.data;
      upsertResource(r);
      setTitle(r.title || '');
      setResourceType(r.resource_type || 'OTHER');
      setUrl(r.url || '');
      setAuthor(r.author || '');
      setPublishedAt(isoToDatetimeLocal(r.published_at));
      setDescription(r.description || '');
      setMyNotes(r.my_notes || '');
      setIsRead(!!r.is_read);
      setRating(typeof r.rating === 'number' ? r.rating : null);
      setAreaId(r.area_id || '');
      setTags(r.tags || []);
    } catch (e) {
      setError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [id, upsertResource]);

  useEffect(() => {
    load();
  }, [load]);

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
      setTags(updated.tags || []);
    } catch {
      // toast from store
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Delete this resource? This cannot be undone.')) return;
    try {
      await deleteResource(id);
      navigate('/resources');
    } catch {
      /* toast */
    }
  };

  const area = areas.find((a) => a.id === areaId);

  if (loading) {
    return (
      <div className={styles.page}>
        <p className={styles.loading}>Loading resource…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.page}>
        <button type="button" className={styles.backBtn} onClick={() => navigate('/resources')}>
          <ArrowLeft size={14} /> All resources
        </button>
        <p className={styles.loading}>{error}</p>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <nav className={styles.breadcrumb} aria-label="Breadcrumb">
        <Link to="/resources">Resources</Link>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{title || 'Resource'}</span>
      </nav>

      <button type="button" className={styles.backBtn} onClick={() => navigate('/resources')}>
        <ArrowLeft size={14} /> All resources
      </button>

      <div className={styles.headerRow}>
        <div className={styles.typeIcon}>
          <ResourceTypeIcon type={resourceType} size={22} />
        </div>
        <div className={styles.headerText}>
          <h1>{title || 'Untitled'}</h1>
          {areaId && (
            <Link to={`/areas/${areaId}`} className={styles.areaLink}>
              <MapPin size={14} />
              {area?.name || 'Area'}
            </Link>
          )}
          {tags.length > 0 && (
            <div className={styles.tags}>
              {tags.map((t) => (
                <span key={t.id} className={styles.tag}>{t.name}</span>
              ))}
            </div>
          )}
        </div>
      </div>

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
              {RESOURCE_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
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
              {areas.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
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
            <span className={styles.label}>Rating</span>
            <div className={styles.starsEdit} role="group" aria-label="Rating 1 to 5">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`${styles.starBtn} ${(rating != null && rating >= n) ? styles.starBtnActive : ''}`}
                  onClick={() => setRating(rating === n ? null : n)}
                  aria-pressed={rating != null && rating >= n}
                  aria-label={`${n} star${n > 1 ? 's' : ''}`}
                >
                  <Star size={20} strokeWidth={2} />
                </button>
              ))}
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRating(null)}>
                Clear
              </button>
            </div>
          </div>
        </div>

        <div className={styles.formActions}>
          <button type="submit" className="btn btn-primary" disabled={saving || !title.trim()}>
            {saving ? 'Saving…' : 'Save changes'}
          </button>
          <button type="button" className="btn btn-ghost" onClick={handleDelete}>
            <Trash2 size={14} /> Delete
          </button>
        </div>
      </form>
    </div>
  );
}
