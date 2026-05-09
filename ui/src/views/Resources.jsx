import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText, BookOpen, Link2, Video, ScrollText, Wrench, Bookmark, Star,
} from 'lucide-react';
import useStore from '../stores/useStore';
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

export default function Resources() {
  const { resources } = useStore();
  const [titleQuery, setTitleQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState(null);

  const filtered = useMemo(() => {
    const q = titleQuery.trim().toLowerCase();
    return resources.filter((r) => {
      if (typeFilter && r.resource_type !== typeFilter) return false;
      if (q && !(r.title || '').toLowerCase().includes(q)) return false;
      return true;
    });
  }, [resources, titleQuery, typeFilter]);

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

      {resources.length === 0 ? (
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
    </div>
  );
}
