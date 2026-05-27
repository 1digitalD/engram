/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { X } from 'lucide-react';
import { v4API } from '../api/v4Client';
import styles from './V4Search.module.css';

const entityTypes = ['', 'note', 'task', 'project', 'area', 'person', 'resource'];
const modes = ['hybrid', 'keyword', 'semantic'];

function entityPath(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

export default function V4Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tagFilter = searchParams.get('tag') || '';
  const [query, setQuery] = useState('');
  const [type, setType] = useState('');
  const [mode, setMode] = useState('hybrid');
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function runSearch({ q, tag } = {}) {
    if (!q && !tag) return;
    setLoading(true);
    setError('');
    try {
      const response = await v4API.search({
        q: q || undefined,
        tag: tag || undefined,
        type: type || undefined,
        mode,
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

  // Auto-run when ?tag= changes in the URL (e.g. clicking a tag chip elsewhere).
  useEffect(() => {
    if (tagFilter) {
      runSearch({ tag: tagFilter });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tagFilter]);

  async function handleSearch(event) {
    event.preventDefault();
    if (!query.trim() || loading) return;
    if (tagFilter) setSearchParams({});
    await runSearch({ q: query.trim() });
  }

  function clearTagFilter() {
    setSearchParams({});
    setResults([]);
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
        {results.length === 0 ? (
          <p>No results yet.</p>
        ) : (
          <ul>
            {results.map((result) => (
              <li key={result.entity.id}>
                <Link to={entityPath(result.entity)}>
                  <span className={styles.type}>{result.entity.type}</span>
                  <strong>{result.entity.title || 'Untitled'}</strong>
                  <small>score {Number(result.score || 0).toFixed(3)}</small>
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
