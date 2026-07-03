import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
import { v4API, friendlyApiError } from '../api/v4Client';
import EntityContextChips from '../components/EntityContextChips';
import XGlyph from '../components/XGlyph';
import { useCapture } from '../context/CaptureContext';
import { hasTaskContext } from '../utils/entityContext';
import { entityTitleLabel } from '../utils/entityDisplay';
import styles from './V5EntityList.module.css';

const COUNT_NOUN = {
  note: ['note', 'notes'],
  task: ['task', 'tasks'],
  project: ['project', 'projects'],
  area: ['area', 'areas'],
  person: ['person', 'people'],
  resource: ['resource', 'resources'],
};

function countNoun(type, count) {
  const [one, other] = COUNT_NOUN[type] || [type, `${type}s`];
  return count === 1 ? one : other;
}

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

function formatDue(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function statusMeta(entity) {
  const parts = [];
  if (entity.type === 'task') {
    const due = formatDue(entity.due_at);
    if (due) parts.push(`due ${due}`);
    else if (entity.follow_up_at) {
      const followUp = formatDue(entity.follow_up_at);
      if (followUp) parts.push(`follow up ${followUp}`);
    }
  }
  if (entity.status) parts.push(entity.status.replace(/_/g, ' '));
  if (entity.properties?.priority) parts.push(entity.properties.priority);
  return parts.join(' · ');
}

function EntityListRow({ entity, type }) {
  const meta = statusMeta(entity);
  const showContext = type === 'task' && hasTaskContext(entity);

  return (
    <li className={styles.listItem}>
      <article className={styles.row}>
        <Link to={detailPath(entity)} className={styles.rowMainLink}>
          <XGlyph type={entity.type} className={styles.rowGlyph} />
          <div className={styles.rowMain}>
            <span className={styles.rowTitle}>
              {entityTitleLabel(entity, { includeType: false })}
            </span>
            {meta && !showContext ? (
              <span className={styles.rowMeta}>{meta}</span>
            ) : null}
          </div>
          {meta && showContext ? (
            <span className={styles.rowBadge}>{meta}</span>
          ) : null}
        </Link>
        {showContext ? (
          <div className={styles.rowFooter}>
            <EntityContextChips
              projects={entity.projects}
              areas={entity.areas}
            />
          </div>
        ) : null}
      </article>
    </li>
  );
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
      const contextTitles = [
        ...(entity.projects || []).map((item) => item.title),
        ...(entity.areas || []).map((item) => item.title),
      ];
      const haystack = [
        entity.title,
        entity.content,
        entity.status,
        entity.properties?.priority,
        ...contextTitles,
      ].filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(normalized);
    });
  }, [entities, query]);

  const title = PLURAL_TITLE[type] || `${type}s`;

  function handleCreate() {
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
        <div className={styles.headerMain}>
          <h1 className={styles.title}>{title}</h1>
          <p className={styles.subtitle}>
            {filtered.length}
            {' '}
            {countNoun(type, filtered.length)}
          </p>
        </div>
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
            <EntityListRow key={entity.id} entity={entity} type={type} />
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
