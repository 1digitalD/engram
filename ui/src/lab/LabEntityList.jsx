import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search } from 'lucide-react';
import { v4API, friendlyApiError } from '../api/v4Client';
import EntityGlyphCircle from '../components/EntityGlyphCircle';
import { entityTitleLabel } from '../utils/entityDisplay';
import styles from './LabEntityList.module.css';

const PLURAL_TITLE = {
  note: 'Notes',
  task: 'Tasks',
  project: 'Projects',
  area: 'Areas',
  person: 'People',
  resource: 'Resources',
};

const EMPTY_HINT = {
  note: 'No notes yet. Capture something from the quick capture sheet.',
  task: 'No tasks yet. Capture a task to get started.',
  project: 'No projects yet. Capture a project idea to get started.',
  area: 'No areas yet. Capture an area to group projects and tasks.',
  person: 'No people yet. Mention someone in a capture to add them.',
  resource: 'No resources yet. Save a link, file, or reference in a capture.',
};

function countNoun(type, count) {
  return count === 1 ? type : `${type}s`;
}

function detailPath(entity) {
  if (entity.type === 'person') return `/people/${entity.id}`;
  return `/${entity.type}s/${entity.id}`;
}

function formatStatus(entity) {
  const parts = [];
  if (entity.status) parts.push(entity.status.replace(/_/g, ' '));
  if (entity.properties?.priority) parts.push(entity.properties.priority);
  return parts.join(' · ');
}

export default function LabEntityList({ type, onOpenCapture }) {
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    v4API.entities.list({
      type, limit: 200, sort: 'updated_at', order: 'desc', lifecycle: 'active',
    })
      .then((response) => {
        if (!active) return;
        setEntities(response?.data || []);
      })
      .catch((err) => {
        if (!active) return;
        setError(friendlyApiError(err, `Failed to load ${type}s`));
        setEntities([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [type]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return entities;
    return entities.filter((entity) => {
      const haystack = [
        entity.title,
        entity.content,
        entity.status,
      ].filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(normalized);
    });
  }, [entities, query]);

  const title = PLURAL_TITLE[type] || `${type}s`;

  if (loading) {
    return (
      <div className={styles.page} aria-busy="true">
        <p className={styles.statusMessage}>Loading {title.toLowerCase()}…</p>
      </div>
    );
  }

  return (
    <div className={styles.page} aria-label={`${title} list`}>
      <header className={styles.header}>
        <div className={styles.headerMain}>
          <h1 className={styles.title}>{title}</h1>
          <p className={styles.subtitle}>
            {filtered.length}
            {' '}
            {countNoun(title.toLowerCase(), filtered.length)}
          </p>
        </div>
        <button
          type="button"
          className={styles.captureButton}
          onClick={onOpenCapture}
          aria-label={`Capture ${type}`}
        >
          Capture
        </button>
      </header>

      <div className={styles.searchWrap}>
        <Search size={14} strokeWidth={2} aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={`Search ${title.toLowerCase()}…`}
          aria-label={`Search ${title}`}
          className={styles.searchInput}
        />
      </div>

      {error ? (
        <p className={styles.errorMessage} role="alert">{error}</p>
      ) : null}

      {filtered.length > 0 ? (
        <ul className={styles.list}>
          {filtered.map((entity) => (
            <li key={entity.id}>
              <Link
                to={detailPath(entity)}
                className={styles.row}
                data-entity-type={entity.type}
              >
                <EntityGlyphCircle type={entity.type} />
                <span className={styles.rowTitle}>
                  {entityTitleLabel(entity, { includeType: false })}
                </span>
                {formatStatus(entity) ? (
                  <span className={styles.rowMeta}>{formatStatus(entity)}</span>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.emptyHint}>
          {query.trim()
            ? `No ${title.toLowerCase()} match "${query.trim()}".`
            : (EMPTY_HINT[type] || `No ${title.toLowerCase()} yet.`)}
        </p>
      )}
    </div>
  );
}
