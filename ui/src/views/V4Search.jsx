/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { X } from 'lucide-react';
import { v4API } from '../api/v4Client';
import { entityTitleLabel } from '../utils/entityDisplay';
import CardActions from '../components/CardActions';
import styles from './V4Search.module.css';

const entityTypes = ['', 'note', 'task', 'project', 'area', 'person', 'resource'];
const modes = ['hybrid', 'keyword', 'semantic'];

function entityPath(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function matchLabel(match = {}) {
  if (match.source === 'tag') return `tag match${match.tag ? `: #${match.tag}` : ''}`;
  if (match.source === 'hybrid') return 'hybrid match';
  if (match.source === 'semantic') return 'semantic match';
  if (match.source === 'keyword') return 'keyword match';
  return 'search match';
}

export default function V4Search() {
  const location = useLocation();
  const fromState = { from: location.pathname + location.search };
  const [searchParams, setSearchParams] = useSearchParams();
  const tagFilter = searchParams.get('tag') || '';
  const queryParam = searchParams.get('q') || '';
  const typeParam = searchParams.get('type') || '';
  const modeParam = searchParams.get('mode') || 'hybrid';
  const [query, setQuery] = useState(queryParam);
  const [type, setType] = useState(typeParam);
  const [mode, setMode] = useState(modeParam);
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const hasActiveSearch = Boolean(queryParam || tagFilter);

  async function runSearch({ q, tag, searchType = type, searchMode = mode } = {}) {
    if (!q && !tag) return;
    setLoading(true);
    setError('');
    try {
      const response = await v4API.search({
        q: q || undefined,
        tag: tag || undefined,
        type: searchType || undefined,
        mode: searchMode,
        limit: 25,
      });
      setResults(response.results || []);
    } catch (err) {
      setError(err.message || 'Search failed');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setQuery(queryParam);
    setType(typeParam);
    setMode(modeParam);
    if (queryParam || tagFilter) {
      runSearch({ q: queryParam, tag: tagFilter, searchType: typeParam, searchMode: modeParam });
    } else {
      setResults([]);
      setError('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryParam, tagFilter, typeParam, modeParam]);

  async function handleSearch(event) {
    event.preventDefault();
    if (!query.trim() || loading) return;
    const next = {};
    if (query.trim()) next.q = query.trim();
    if (tagFilter) next.tag = tagFilter;
    if (type) next.type = type;
    if (mode && mode !== 'hybrid') next.mode = mode;
    setSearchParams(next);
  }

  function clearTagFilter() {
    const next = {};
    if (queryParam) next.q = queryParam;
    if (typeParam) next.type = typeParam;
    if (modeParam && modeParam !== 'hybrid') next.mode = modeParam;
    setSearchParams(next);
  }

  return (
    <main className={styles.search}>
      <section className={styles.hero}>
        {tagFilter && (
          <div className={styles.tagFilterChip} role="status">
            <span>Filtered by tag</span>
            <strong>#{tagFilter}</strong>
            <button type="button" onClick={clearTagFilter} aria-label="Clear tag filter" title="Clear">
              <X size={12} strokeWidth={2.4} aria-hidden="true" />
            </button>
          </div>
        )}
        <form onSubmit={handleSearch} className={styles.form} aria-label="Search entities">
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Query</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search notes, tasks, projects, people, resources..."
              aria-label="Search query"
            />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Type</span>
            <select value={type} onChange={(event) => setType(event.target.value)} aria-label="Entity type">
              {entityTypes.map((option) => (
                <option key={option || 'all'} value={option}>{option || 'all types'}</option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Mode</span>
            <select value={mode} onChange={(event) => setMode(event.target.value)} aria-label="Search mode">
              {modes.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={!query.trim() || loading}>
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>
        {error && <div className={styles.error}>{error}</div>}
      </section>

      <section className={styles.results}>
        <h2>Results</h2>
        {loading ? (
          <p className={styles.emptyState}>Searching…</p>
        ) : results.length === 0 ? (
          <p className={styles.emptyState}>
            {hasActiveSearch ? 'No results matched this search.' : 'Search by text or jump in from a tag.'}
          </p>
        ) : (
          <ul>
            {results.map((result) => (
              <li key={result.entity.id} className="cardActionsParent">
                <CardActions
                  entity={result.entity}
                  onChanged={() => setResults((cur) => cur.filter((r) => r.entity.id !== result.entity.id))}
                />
                <Link to={entityPath(result.entity)} state={fromState}>
                  <div className={styles.metaRow}>
                    <span className={styles.type}>{result.entity.type}</span>
                    <span className={styles.status}>{result.entity.status}</span>
                    <span className={styles.matchMeta}>{matchLabel(result.match)}</span>
                  </div>
                  <strong>{entityTitleLabel(result.entity)}</strong>
                  {result.entity.tags?.length ? (
                    <div className={styles.tagRow}>
                      {result.entity.tags.slice(0, 3).map((tag) => (
                        <span key={tag.id || tag.name} className={styles.tagChip}>#{tag.name}</span>
                      ))}
                    </div>
                  ) : null}
                  {result.match?.snippet && <p>{result.match.snippet}</p>}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
