import { useState, useEffect, useRef, useCallback } from 'react';
import XGlyph from './XGlyph';
import { pathForEntityType } from '../utils/entityContext';
import { v4API } from '../api/v4Client';
import styles from './EntityPicker.module.css';

export default function EntityPicker({ entityType, value, onChange, placeholder }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const activeIdxRef = useRef(-1);

  // Focus input when opening
  const doOpen = useCallback(() => {
    setOpen(true);
    setQuery('');
    setResults([]);
    activeIdxRef.current = -1;
  }, []);

  const doClose = useCallback(() => {
    setOpen(false);
    setQuery('');
    setResults([]);
    activeIdxRef.current = -1;
  }, []);

  // Search on query change
  useEffect(() => {
    if (!open || query.length < 2) {
      setResults([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    v4API.search({ q: query, type: entityType, limit: 10 }).then((resp) => {
      if (cancelled) return;
      setResults(resp?.results || []);
      setLoading(false);
    }).catch(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [query, open, entityType]);

  // Scroll active result into view
  useEffect(() => {
    if (activeIdxRef.current >= 0 && listRef.current) {
      const item = listRef.current.children[activeIdxRef.current];
      if (item) item.scrollIntoView({ block: 'nearest' });
    }
  }, [results]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      doClose();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIdxRef.current = Math.min(activeIdxRef.current + 1, results.length - 1);
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIdxRef.current = Math.max(activeIdxRef.current - 1, 0);
      return;
    }
    if (e.key === 'Enter' && activeIdxRef.current >= 0) {
      e.preventDefault();
      const entity = results[activeIdxRef.current]?.entity;
      if (entity) {
        onChange({ id: entity.id, title: entity.title });
        doClose();
      }
      return;
    }
  }, [results, doClose, onChange]);

  const handleSelect = useCallback((entity) => {
    onChange({ id: entity.id, title: entity.title });
    doClose();
  }, [onChange, doClose]);

  const handleClear = useCallback(() => {
    onChange(null);
    doClose();
  }, [onChange, doClose]);

  return (
    <div className={styles.wrapper}>
      {value ? (
        <div className={styles.selected} role="button" tabIndex={0} onClick={doOpen} onKeyDown={(e) => e.key === 'Enter' && doOpen()}>
          <XGlyph type={entityType === 'project' ? 'project' : 'area'} />
          <span className={styles.selectedLabel}>{value.title}</span>
          <button type="button" className={styles.clearBtn} onClick={(e) => { e.stopPropagation(); handleClear(); }} aria-label="Clear">
            ×
          </button>
        </div>
      ) : (
        <input
          ref={inputRef}
          className={styles.input}
          type="text"
          placeholder={placeholder || `Search ${entityType}s…`}
          value={open ? query : ''}
          onFocus={doOpen}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => setTimeout(doClose, 200)}
        />
      )}

      {open && query.length >= 2 && (
        <div className={styles.dropdown} ref={listRef}>
          {loading ? (
            <div className={styles.statusItem}>Searching…</div>
          ) : results.length === 0 ? (
            <div className={styles.statusItem}>No results</div>
          ) : (
            results.map((result, idx) => {
              const entity = result.entity;
              return (
                <div
                  key={entity.id}
                  className={`${styles.resultItem} ${idx === activeIdxRef.current ? styles.active : ''}`}
                  onMouseDown={() => handleSelect(entity)}
                  onMouseEnter={() => { activeIdxRef.current = idx; }}
                >
                  <XGlyph type={entityType === 'project' ? 'project' : 'area'} />
                  <span className={styles.resultLabel}>{entity.title}</span>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
