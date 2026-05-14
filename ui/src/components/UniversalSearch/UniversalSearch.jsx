import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, FileText, FolderOpen, Map, Users, CheckSquare,
  Library, ArrowRight, X
} from 'lucide-react';
import useStore from '../../stores/useStore';
import styles from './UniversalSearch.module.css';

export const ENTITY_TYPES = ['note', 'task', 'project', 'area', 'resource', 'person'];

const TYPE_CONFIG = {
  note:     { icon: FileText,   label: 'Notes',     color: 'var(--accent)' },
  task:     { icon: CheckSquare, label: 'Tasks',     color: 'var(--accent)' },
  project:  { icon: FolderOpen,  label: 'Projects',  color: 'var(--accent)' },
  area:     { icon: Map,         label: 'Areas',     color: 'var(--accent)' },
  resource: { icon: Library,     label: 'Resources', color: 'var(--accent)' },
  person:   { icon: Users,       label: 'People',    color: 'var(--accent)' },
};

export function getEntityTitle(entity, type) {
  switch (type) {
    case 'note':
      return (entity.raw_text || '').split('\n')[0].replace(/^#\s*/, '').trim() || 'Untitled';
    case 'task':
      return entity.title || 'Untitled';
    default:
      return entity.title || 'Untitled';
  }
}

export function getEntityRoute(id, type) {
  switch (type) {
    case 'note':    return `/notes/${id}`;
    case 'project': return `/projects/${id}`;
    case 'area':    return `/areas/${id}`;
    case 'person':  return '/people';
    case 'task':    return '/tasks';
    case 'resource': return '/resources';
    default:        return '/';
  }
}

function searchInStore(store, query) {
  const q = query.toLowerCase();
  const groups = {};

  const storeKeys = {
    note: 'notes',
    task: 'tasks',
    project: 'projects',
    area: 'areas',
    resource: 'resources',
    person: 'people',
  };

  ENTITY_TYPES.forEach(type => {
    const items = (store[storeKeys[type]] || []).filter(item => {
      const title = getEntityTitle(item, type).toLowerCase();
      return title.includes(q);
    }).slice(0, 5);

    if (items.length > 0) {
      groups[type] = items;
    }
  });

  return groups;
}

export default function UniversalSearch({ onClose }) {
  const navigate = useNavigate();
  const store = useStore();
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef(null);
  const resultsListRef = useRef(null);

  const groupedResults = useMemo(() => {
    if (!query.trim()) return {};
    return searchInStore(store, query.trim());
  }, [store, query]);

  const flatResults = useMemo(() => {
    const flat = [];
    ENTITY_TYPES.forEach(type => {
      if (groupedResults[type]) {
        groupedResults[type].forEach(item => {
          flat.push({ type, item });
        });
      }
    });
    return flat;
  }, [groupedResults]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    if (resultsListRef.current) {
      const activeEl = resultsListRef.current.querySelector(`.${styles.resultActive}`);
      if (activeEl && typeof activeEl.scrollIntoView === 'function') {
        activeEl.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [activeIndex]);

  const handleSelect = useCallback((type, item) => {
    const route = getEntityRoute(item.id, type);
    navigate(route);
    onClose();
  }, [navigate, onClose]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      onClose();
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(prev => Math.min(prev + 1, flatResults.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (flatResults[activeIndex]) {
        handleSelect(flatResults[activeIndex].type, flatResults[activeIndex].item);
      }
    }
  }, [flatResults, activeIndex, handleSelect, onClose]);

  const totalResults = flatResults.length;

  return (
    <div className={styles.backdrop} onClick={onClose} data-testid="universal-search-backdrop">
      <div
        className={styles.palette}
        onClick={e => e.stopPropagation()}
        data-testid="universal-search-palette"
      >
        <div className={styles.inputRow}>
          <Search size={16} className={styles.searchIcon} />
          <input
            ref={inputRef}
            className={styles.input}
            data-testid="universal-search-input"
            placeholder="Search notes, tasks, projects, areas, resources, people…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          {query && (
            <button
              type="button"
              className={styles.clearBtn}
              onClick={() => setQuery('')}
              aria-label="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {query.trim() && (
          <div className={styles.results} ref={resultsListRef} data-testid="search-results">
            {totalResults === 0 && (
              <div className={styles.empty}>No results for &ldquo;{query}&rdquo;</div>
            )}

            {ENTITY_TYPES.map(type => {
              const items = groupedResults[type];
              if (!items || items.length === 0) return null;

              const config = TYPE_CONFIG[type];
              const Icon = config.icon;

              let globalStartIndex = 0;
              for (const t of ENTITY_TYPES) {
                if (t === type) break;
                globalStartIndex += (groupedResults[t] || []).length;
              }

              return (
                <div key={type} className={styles.group} data-testid={`group-${type}`}>
                  <div className={styles.groupHeader}>
                    <Icon size={13} className={styles.groupIcon} />
                    <span>{config.label}</span>
                    <span className={styles.groupCount}>{items.length}</span>
                  </div>
                  {items.map((item, idx) => {
                    const globalIdx = globalStartIndex + idx;
                    const isActive = globalIdx === activeIndex;
                    return (
                      <button
                        key={`${type}-${item.id}`}
                        type="button"
                        className={`${styles.result} ${isActive ? styles.resultActive : ''}`}
                        data-testid={`result-${type}-${item.id}`}
                        onClick={() => handleSelect(type, item)}
                        onMouseEnter={() => setActiveIndex(globalIdx)}
                      >
                        <Icon size={14} className={styles.resultIcon} />
                        <div className={styles.resultContent}>
                          <span className={styles.resultTitle}>
                            {getEntityTitle(item, type)}
                          </span>
                        </div>
                        <ArrowRight size={12} className={styles.resultArrow} />
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        )}

        {totalResults > 0 && (
          <div className={styles.footer}>
            <span><kbd>&uarr;&darr;</kbd> navigate</span>
            <span>&middot;</span>
            <span><kbd>&crarr;</kbd> open</span>
            <span>&middot;</span>
            <span><kbd>esc</kbd> close</span>
            <span className={styles.footerCount}>{totalResults} result{totalResults !== 1 ? 's' : ''}</span>
          </div>
        )}
      </div>
    </div>
  );
}
