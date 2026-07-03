import {
  useCallback, useEffect, useMemo, useRef, useState,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, Sparkles } from 'lucide-react';
import Sheet from '../components/Sheet';
import { v4API, friendlyApiError } from '../api/v4Client';
import XGlyph from '../components/XGlyph';
import { useCapture } from '../context/CaptureContext';
import { normalizeSearchResults } from '../utils/searchResults';
import EntityContextChips from '../components/EntityContextChips';
import { hasTaskContext } from '../utils/entityContext';
import styles from './V5Recall.module.css';

const DEBOUNCE_MS = 180;

const TYPE_LABEL = {
  note: 'Notes',
  task: 'Tasks',
  project: 'Projects',
  area: 'Areas',
  person: 'People',
  resource: 'Resources',
};

function detailPath(entity) {
  if (entity.type === 'person') return `/people/${entity.id}`;
  return `/${entity.type}s/${entity.id}`;
}

function groupLabel(type) {
  return TYPE_LABEL[type] || `${type || 'unknown'}s`;
}

function statusClass(status) {
  if (!status) return '';
  if (status === 'blocked') return styles.statusBlocked;
  if (status === 'waiting') return styles.statusWaiting;
  if (status === 'done' || status === 'cancelled') return styles.statusDone;
  return '';
}

function groupResults(results) {
  const groups = new Map();
  for (const entity of results) {
    const type = entity.type || 'unknown';
    if (!groups.has(type)) groups.set(type, []);
    groups.get(type).push(entity);
  }
  return [...groups.entries()].map(([type, items]) => ({ type, items }));
}

function useRecallSearch(query) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const timerRef = useRef(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setLoading(false);
      setError('');
      return undefined;
    }

    setLoading(true);
    setError('');

    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
    }

    const requestId = ++requestIdRef.current;
    timerRef.current = window.setTimeout(() => {
      v4API.search({ q: trimmed, limit: 24 })
        .then((response) => {
          if (requestId !== requestIdRef.current) return;
          setResults(normalizeSearchResults(response));
        })
        .catch((err) => {
          if (requestId !== requestIdRef.current) return;
          setError(friendlyApiError(err, 'Search failed'));
          setResults([]);
        })
        .finally(() => {
          if (requestId !== requestIdRef.current) return;
          setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [query]);

  return { results, loading, error };
}

export default function V5Recall({ open, onClose, onAsk, initialQuery = '' }) {
  const navigate = useNavigate();
  const { openCapture } = useCapture();
  const [query, setQuery] = useState(initialQuery);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const { results, loading, error } = useRecallSearch(query);

  const flatResults = useMemo(() => results, [results]);
  const grouped = useMemo(() => groupResults(flatResults), [flatResults]);

  useEffect(() => {
    if (open) {
      setQuery(initialQuery);
      setSelectedIndex(0);
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open, initialQuery]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query, results.length]);

  const selectEntity = useCallback((entity) => {
    if (!entity) return;
    onClose?.();
    navigate(detailPath(entity));
  }, [navigate, onClose]);

  const handleKeyDown = useCallback((event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setSelectedIndex((idx) => (idx + 1) % Math.max(flatResults.length, 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setSelectedIndex((idx) => (idx - 1 + Math.max(flatResults.length, 1)) % Math.max(flatResults.length, 1));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (flatResults[selectedIndex]) {
        selectEntity(flatResults[selectedIndex]);
      }
    }
  }, [flatResults, selectedIndex, selectEntity]);

  return (
    <Sheet open={open} onClose={onClose} ariaLabel="Recall search" mobileBottomSheet>
      <div className={styles.recall}>
        <header className={styles.header}>
          <div className={styles.inputWrap}>
            <Search size={16} strokeWidth={2.2} aria-hidden="true" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search your workspace"
              aria-label="Search terms"
              className={styles.input}
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck="false"
            />
          </div>
          {query.trim() ? (
            <button
              type="button"
              className={styles.askButton}
              onClick={() => {
                onClose?.();
                openCapture(query);
              }}
              aria-label={`Capture ${query}`}
            >
              <Plus size={14} strokeWidth={2.2} aria-hidden="true" />
              Capture
            </button>
          ) : null}
        </header>

        <div className={styles.body} role="listbox" aria-label="Search results">
          {error ? (
            <p className={styles.message} role="alert">{error}</p>
          ) : null}

          {loading ? (
            <p className={styles.message}>Searching…</p>
          ) : null}

          {!loading && !error && query.trim() && flatResults.length === 0 ? (
            <div className={styles.emptyState}>
              <p className={styles.message}>No results for "{query.trim()}".</p>
              <button
                type="button"
                className={styles.handoffButton}
                onClick={() => {
                  onClose?.();
                  onAsk?.();
                }}
              >
                <Sparkles size={14} strokeWidth={2.2} aria-hidden="true" />
                Open Ask Engram
              </button>
            </div>
          ) : null}

          {!loading && !query.trim() ? (
            <p className={styles.message}>Type to search across notes, tasks, projects, people, and resources.</p>
          ) : null}

          {grouped.map((group) => (
            <section key={group.type} className={styles.group} data-entity-type={group.type}>
              <h2 className={styles.groupLabel}>
                <span className={styles.groupDot} aria-hidden="true" />
                {groupLabel(group.type)}
                <span className={styles.groupCount}>{group.items.length}</span>
              </h2>
              <ul className={styles.groupList}>
                {group.items.map((entity) => {
                  const globalIndex = flatResults.indexOf(entity);
                  const selected = globalIndex === selectedIndex;
                  return (
                    <li key={entity.id} role="option" aria-selected={selected}>
                      <div
                        className={`${styles.resultCard} ${selected ? styles.resultCardSelected : ''}`}
                        onMouseEnter={() => setSelectedIndex(globalIndex)}
                      >
                        <button
                          type="button"
                          className={`${styles.result} ${selected ? styles.resultSelected : ''}`}
                          data-entity-type={entity.type}
                          onClick={() => selectEntity(entity)}
                        >
                          <XGlyph type={entity.type} className={styles.resultGlyph} />
                          <span className={styles.resultMain}>
                            <span className={styles.resultTitle}>{entity.title || '(no title)'}</span>
                            {entity.searchSnippet ? (
                              <span className={styles.resultSnippet}>{entity.searchSnippet}</span>
                            ) : null}
                          </span>
                          {entity.status ? (
                            <span className={`${styles.resultMeta} ${statusClass(entity.status)}`}>
                              {entity.status.replace(/_/g, ' ')}
                            </span>
                          ) : null}
                        </button>
                        {entity.type === 'task' && hasTaskContext(entity) ? (
                          <div className={styles.resultFooter}>
                            <EntityContextChips
                              projects={entity.projects}
                              areas={entity.areas}
                              people={entity.people}
                              className={styles.resultContext}
                            />
                          </div>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>

        <footer className={styles.footer}>
          <span className={styles.footerHint}>
            <kbd>↑</kbd>
            <kbd>↓</kbd>
            to navigate ·
            <kbd>↵</kbd>
            to open ·
            <kbd>esc</kbd>
            to close
          </span>
        </footer>
      </div>
    </Sheet>
  );
}
