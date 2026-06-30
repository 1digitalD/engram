import {
  useCallback, useEffect, useMemo, useRef, useState,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Sparkles } from 'lucide-react';
import Sheet from '../components/Sheet';
import { v4API } from '../api/v4Client';
import XGlyph from '../components/XGlyph';
import styles from './V5Recall.module.css';

const DEBOUNCE_MS = 180;

function detailPath(entity) {
  if (entity.type === 'person') return `/people/${entity.id}`;
  return `/${entity.type}s/${entity.id}`;
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

    timerRef.current = window.setTimeout(() => {
      v4API.search({ q: trimmed, limit: 24 })
        .then((response) => {
          setResults(response?.data || []);
        })
        .catch((err) => {
          setError(err.message || 'Search failed');
          setResults([]);
        })
        .finally(() => {
          setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [query]);

  return { results, loading, error };
}

export default function V5Recall({ open, onClose, initialQuery = '' }) {
  const navigate = useNavigate();
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
      // Focus on next tick so the sheet is mounted.
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
              placeholder="Search or ask…"
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
                navigate('/', { state: { capture: true, recallQuery: query } });
              }}
              aria-label={`Ask about ${query}`}
            >
              <Sparkles size={14} strokeWidth={2.2} aria-hidden="true" />
              Ask
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
            <p className={styles.message}>No results for "{query.trim()}".</p>
          ) : null}

          {!loading && !query.trim() ? (
            <p className={styles.message}>Type to search across notes, tasks, projects, people, and resources.</p>
          ) : null}

          {grouped.map((group) => (
            <section key={group.type} className={styles.group}>
              <h2 className={styles.groupLabel}>{group.type}s</h2>
              <ul className={styles.groupList}>
                {group.items.map((entity) => {
                  const globalIndex = flatResults.indexOf(entity);
                  const selected = globalIndex === selectedIndex;
                  return (
                    <li key={entity.id} role="option" aria-selected={selected}>
                      <button
                        type="button"
                        className={`${styles.result} ${selected ? styles.resultSelected : ''}`}
                        onClick={() => selectEntity(entity)}
                        onMouseEnter={() => setSelectedIndex(globalIndex)}
                      >
                        <XGlyph type={entity.type} />
                        <span className={styles.resultTitle}>{entity.title || '(no title)'}</span>
                        {entity.status ? (
                          <span className={styles.resultMeta}>{entity.status.replace(/_/g, ' ')}</span>
                        ) : null}
                      </button>
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
