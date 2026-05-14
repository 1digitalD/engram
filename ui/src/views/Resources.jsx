import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText, BookOpen, Link2, Video, ScrollText, Wrench, Bookmark, Star,
  Loader2, Sparkles, Plus,
} from 'lucide-react';
import useStore from '../stores/useStore';
import Modal from '../components/ui/Modal';
import { resourcesAPI } from '../api/engram';
import EmptyState from '../components/ui/EmptyState';
import styles from './Resources.module.css';

export const RESOURCE_TYPES = [
  'ARTICLE', 'BOOK', 'URL', 'VIDEO', 'PAPER', 'TOOL', 'OTHER',
];

const TYPE_ICONS = {
  ARTICLE: FileText,
  BOOK: BookOpen,
  URL: Link2,
  VIDEO: Video,
  PAPER: ScrollText,
  TOOL: Wrench,
  OTHER: Bookmark,
};

export function ResourceTypeIcon({ type, size = 18 }) {
  const Icon = TYPE_ICONS[type] || Bookmark;
  return <Icon size={size} strokeWidth={2} aria-hidden />;
}

function RatingStars({ value }) {
  const v = typeof value === 'number' ? value : 0;
  return (
    <span className={styles.stars} aria-label={v ? `Rating ${v} of 5` : 'No rating'}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} size={14} className={i <= v ? styles.starFilled : styles.starEmpty} />
      ))}
    </span>
  );
}

function normalizeResource(resource) {
  const props = resource.properties || {};
  return {
    ...resource,
    resource_type: resource.resource_type || props.resource_type || 'OTHER',
    author: resource.author || props.author || '',
    is_read: resource.is_read ?? props.is_read ?? false,
    rating: resource.rating ?? props.rating ?? null,
  };
}

export default function Resources() {
  const { resources, areas, loadAll, addToast, loading } = useStore();
  const [titleQuery, setTitleQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [formTitle, setFormTitle] = useState('');
  const [formType, setFormType] = useState('ARTICLE');
  const [formUrl, setFormUrl] = useState('');
  const [formAuthor, setFormAuthor] = useState('');
  const [formAreaId, setFormAreaId] = useState('');
  const [formTags, setFormTags] = useState('');

  const filtered = useMemo(() => {
    const q = titleQuery.trim().toLowerCase();
    return resources.map(normalizeResource).filter((r) => {
      if (typeFilter && r.resource_type !== typeFilter) return false;
      if (q && !(r.title || '').toLowerCase().includes(q)) return false;
      return true;
    });
  }, [resources, titleQuery, typeFilter]);

  const resetForm = () => {
    setFormTitle('');
    setFormType('ARTICLE');
    setFormUrl('');
    setFormAuthor('');
    setFormAreaId('');
    setFormTags('');
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!formTitle.trim()) return;
    try {
      await resourcesAPI.create({
        title: formTitle.trim(),
        resource_type: formType,
        url: formUrl.trim() || undefined,
        author: formAuthor.trim() || undefined,
        area_id: formAreaId || undefined,
        tags: formTags.trim() || undefined,
        source: 'manual',
      });
      resetForm();
      setShowModal(false);
      loadAll();
      addToast({ type: 'success', message: 'Resource created' });
    } catch (e) {
      addToast({ type: 'error', message: e.message });
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Resources</h1>
          <p className={styles.count}>{filtered.length} shown · {resources.length} total</p>
          <p className={styles.hint}>
            Typed references — articles, books, links, and other materials. Filter by kind or search by title.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={15} /> New Resource
        </button>
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchRow}>
          <input
            type="search"
            className={styles.searchInput}
            placeholder="Search by title…"
            value={titleQuery}
            onChange={(e) => setTitleQuery(e.target.value)}
            aria-label="Filter by title"
          />
        </div>
        <div className={styles.chips} role="group" aria-label="Filter by resource type">
          <button
            type="button"
            className={`${styles.chip} ${typeFilter === null ? styles.chipActive : ''}`}
            onClick={() => setTypeFilter(null)}
          >
            All
          </button>
          {RESOURCE_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              className={`${styles.chip} ${typeFilter === t ? styles.chipActive : ''}`}
              onClick={() => setTypeFilter((cur) => (cur === t ? null : t))}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {loading && resources.length === 0 ? (
        <Loader2 size={20} className="spin" style={{ display: 'block', margin: '40px auto', color: 'var(--text-muted)' }} />
      ) : resources.length === 0 ? (
        <EmptyState
          type="notes"
          title="No resources yet"
          message="Create resources via the API or future capture flows. They will appear here with type, rating, and links to areas."
        />
      ) : filtered.length === 0 ? (
        <p className={styles.hint}>No resources match your filters.</p>
      ) : (
        <div className={styles.grid}>
          {filtered.map((r) => (
            <Link key={r.id} to={`/resources/${r.id}`} className={styles.card}>
              <div className={styles.cardTop}>
                <div className={styles.typeIcon}>
                  <ResourceTypeIcon type={r.resource_type} />
                </div>
                <div className={styles.cardBody}>
                  <h2 className={styles.title}>{r.title}</h2>
                  {r.author && <p className={styles.author}>{r.author}</p>}
                </div>
                {r.ai_status === 'processing' && (
                  <span className={styles.aiProcessing}><Loader2 size={12} className="spin" /></span>
                )}
                {r.ai_status === 'done' && r._ai_meta?.bucket && (
                  <span className={styles.aiClassification}>
                    <Sparkles size={10} />
                    {r._ai_meta.bucket}
                  </span>
                )}
              </div>
              <div className={styles.metaRow}>
                <span className={styles.typePill}>{r.resource_type}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                  <span
                    className={`${styles.readBadge} ${r.is_read ? styles.readBadgeDone : ''}`}
                  >
                    {r.is_read ? 'Read' : 'Unread'}
                  </span>
                  <RatingStars value={r.rating} />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {showModal && (
        <Modal isOpen onClose={() => { resetForm(); setShowModal(false); }} title="New Resource" footer={
          <><button className="btn btn-ghost" onClick={() => { resetForm(); setShowModal(false); }}>Cancel</button>
          <button className="btn btn-primary" onClick={handleCreate} disabled={!formTitle.trim()}>Create</button></>
        }>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div>
              <label className={styles.label}>Title</label>
              <input value={formTitle} onChange={e => setFormTitle(e.target.value)} placeholder="Resource title" autoFocus />
            </div>
            <div>
              <label className={styles.label}>Resource Type</label>
              <select value={formType} onChange={e => setFormType(e.target.value)}>
                {RESOURCE_TYPES.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={styles.label}>URL</label>
              <input value={formUrl} onChange={e => setFormUrl(e.target.value)} placeholder="https://..." />
            </div>
            <div>
              <label className={styles.label}>Author</label>
              <input value={formAuthor} onChange={e => setFormAuthor(e.target.value)} placeholder="Author name" />
            </div>
            <div>
              <label className={styles.label}>Area</label>
              <select value={formAreaId} onChange={e => setFormAreaId(e.target.value)}>
                <option value="">None</option>
                {areas.map(a => (
                  <option key={a.id} value={a.id}>{a.title}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={styles.label}>Tags</label>
              <input value={formTags} onChange={e => setFormTags(e.target.value)} placeholder="Comma-separated tags" />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
