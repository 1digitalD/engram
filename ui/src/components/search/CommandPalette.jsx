import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, FileText, FolderOpen, Map, Users, CheckSquare,
  Network, ArrowRight, Hash, Inbox, Plus, X, Calendar
} from 'lucide-react';
import useStore from '../../stores/useStore';
import styles from './CommandPalette.module.css';

const ICON_MAP = {
  note: FileText, project: FolderOpen, area: Map,
  person: Users, task: CheckSquare, graph: Network,
};

export default function CommandPalette({ onClose }) {
  const navigate = useNavigate();
  const { notes, projects, areas, people, tasks, searchNotes } = useStore();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Search as user types
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      const q = query.toLowerCase();
      // Filter locally first
      const localResults = [
        ...notes.filter(n => n.raw_text?.toLowerCase().includes(q))
          .slice(0, 5).map(n => ({ type: 'note', item: n })),
        ...projects.filter(p => p.name?.toLowerCase().includes(q))
          .map(p => ({ type: 'project', item: p })),
        ...areas.filter(a => a.name?.toLowerCase().includes(q))
          .map(a => ({ type: 'area', item: a })),
        ...people.filter(p => p.name?.toLowerCase().includes(q))
          .map(p => ({ type: 'person', item: p })),
        ...tasks.filter(t => t.title?.toLowerCase().includes(q))
          .slice(0, 3).map(t => ({ type: 'task', item: t })),
      ];
      setResults(localResults);
      setActiveIndex(0);
      setLoading(false);
    }, 200);
  }, [query]);

  const handleSelect = useCallback((result) => {
    if (!result) return;
    const { type, item } = result;
    switch (type) {
      case 'note':    navigate(`/notes/${item.id}`); break;
      case 'project': navigate(`/projects/${item.id}`); break;
      case 'area':    navigate(`/areas`); break;
      case 'person':  navigate(`/people`); break;
      case 'task':    navigate(`/tasks`); break;
      default: break;
    }
    onClose();
  }, [navigate, onClose]);

  const handleKey = (e) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(i => Math.min(i + 1, results.length - 1));
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(i => Math.max(i - 1, 0));
    }
    if (e.key === 'Enter' && results[activeIndex]) {
      handleSelect(results[activeIndex]);
    }
  };

  const quickActions = !query && [
    { label: 'Capture note', action: () => navigate('/notes'), icon: Inbox },
    { label: 'New project', action: () => navigate('/projects'), icon: Plus },
    { label: 'View tasks', action: () => navigate('/tasks'), icon: CheckSquare },
    { label: 'View graph', action: () => navigate('/graph'), icon: Network },
    { label: 'Weekly review', action: () => navigate('/review'), icon: Calendar },
  ];

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.palette} onClick={e => e.stopPropagation()}>
        {/* Input */}
        <div className={styles.inputRow}>
          <Search size={16} className={styles.searchIcon} />
          <input
            ref={inputRef}
            className={styles.input}
            placeholder="Search notes, projects, people... or type a command"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
          />
          {loading && <div className="spinner" />}
          {query && !loading && (
            <button onClick={() => setQuery('')} className={styles.clearBtn}>
              <X size={14} />
            </button>
          )}
        </div>

        {/* Results */}
        {query && (
          <div className={styles.results}>
            {results.length === 0 && !loading && (
              <div className={styles.empty}>No results for "{query}"</div>
            )}
            {results.map((r, i) => {
              const Icon = ICON_MAP[r.type] || FileText;
              return (
                <button
                  key={`${r.type}-${r.item.id}`}
                  className={`${styles.result} ${i === activeIndex ? styles.resultActive : ''}`}
                  onClick={() => handleSelect(r)}
                  onMouseEnter={() => setActiveIndex(i)}
                >
                  <Icon size={14} className={styles.resultIcon} />
                  <div className={styles.resultContent}>
                    <span className={styles.resultTitle}>
                      {r.item.name || r.item.title || r.item.raw_text?.slice(0, 60)}
                    </span>
                    <span className={styles.resultType}>{r.type}</span>
                  </div>
                  <ArrowRight size={12} className={styles.resultArrow} />
                </button>
              );
            })}
          </div>
        )}

        {/* Quick Actions */}
        {!query && (
          <div className={styles.quick}>
            <div className={styles.quickLabel}>Quick actions</div>
            {quickActions.map((a, i) => {
              const Icon = a.icon;
              return (
                <button
                  key={a.label}
                  className={styles.result}
                  onClick={() => { a.action(); onClose(); }}
                >
                  <Icon size={14} className={styles.resultIcon} />
                  <span className={styles.resultTitle}>{a.label}</span>
                </button>
              );
            })}
          </div>
        )}

        <div className={styles.footer}>
          <kbd>↑↓</kbd> navigate · <kbd>↵</kbd> select · <kbd>esc</kbd> close
        </div>
      </div>
    </div>
  );
}
