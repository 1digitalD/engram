import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
import { v4API, friendlyApiError } from '../api/v4Client';
import { entityTitleLabel } from '../utils/entityDisplay';
import XGlyph from '../components/XGlyph';
import { useCapture } from '../context/CaptureContext';
import styles from './V5EntityList.module.css';

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

function detailPath(entity) {
  if (entity.type === 'person') return `/people/${entity.id}`;
  return `/${entity.type}s/${entity.id}`;
}

function statusMeta(entity) {
  const parts = [];
  if (entity.status) parts.push(entity.status.replace(/_/g, ' '));
  if (entity.properties?.priority) parts.push(entity.properties.priority);
  return parts.join(' · ');
}

export default function V5EntityList({ type }) {
  const { openCapture } = useCapture();
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    v4API.entities.list({ type, limit: 200, sort: 'updated_at', order: 'desc' })
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
        entity.properties?.priority,
      ].filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(normalized);
    });
  }, [entities, query]);

  const title = PLURAL_TITLE[type] || `${type}s`;

  function handleCreate() {
    // Entity list screens are capture-first: the New button opens the capture
    // sheet so the source note is preserved and the agent can extract the
    // requested entity. The attachment defaults to the current thread when
    // inside a thread, and is empty on list routes.
    openCapture();
  }

  if (loading) {
    return (
      <main className={styles.page} aria-busy="true">
        <p className={styles.statusMessage}>Loading {title.toLowerCase()}…</p>
      </main>
    );
  }

  return (
    <main className={styles.page} aria-label={`${title} list`}>
      <header className={styles.header}>
        <h1 className={styles.title}>{title}</h1>
        <button
          type="button"
          className={styles.createButton}
          onClick={handleCreate}
          aria-label={`Capture ${type}`}
        >
          <Plus size={16} strokeWidth={2.4} aria-hidden="true" />
          <span>Capture</span>
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
              <Link to={detailPath(entity)} className={styles.row}>
                <XGlyph type={entity.type} />
                <div className={styles.rowMain}>
                  <span className={styles.rowTitle}>
                    {entityTitleLabel(entity, { includeType: false })}
                  </span>
                  {statusMeta(entity) ? (
                    <span className={styles.rowMeta}>{statusMeta(entity)}</span>
                  ) : null}
                </div>
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
    </main>
  );
}
