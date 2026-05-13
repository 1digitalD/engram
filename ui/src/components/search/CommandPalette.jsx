import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, FileText, FolderOpen, Map, Users, CheckSquare,
  Network, ArrowRight, Hash, Inbox, Plus, X, Calendar,
  Zap, LayoutDashboard
} from 'lucide-react';
import useStore from '../../stores/useStore';
import styles from './CommandPalette.module.css';

const ICON_MAP = {
  note: FileText, project: FolderOpen, area: Map,
  person: Users, task: CheckSquare, graph: Network, command: Plus,
};

const ENTITY_LABELS = {
  note: 'note', project: 'project', area: 'area',
  person: 'person', task: 'task', command: 'command',
};

function paletteShortcutLabel() {
  if (typeof navigator === 'undefined') return '⌘K';
  return /Mac|iPhone|iPad|iPod/i.test(navigator.userAgent) ? '⌘K' : 'Ctrl+K';
}

function highlightMatch(text, query) {
  if (!query || !text) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <span className={styles.matchHighlight}>{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}

function getSubtitle(type, item) {
  switch (type) {
    case 'note':
      return item.raw_text?.slice(0, 80) || '';
    case 'project':
      return item.status || 'project';
    case 'area':
      return 'area';
    case 'person':
      return item.role || 'person';
    case 'task':
      return item.status || 'task';
    case 'command':
      return item.subtitle || '';
    default:
      return type;
  }
}

function getTitle(type, item) {
  switch (type) {
    case 'command':
      return item.label;
    case 'note':
      return item.raw_text?.slice(0, 60) || 'Untitled note';
    default:
      return item.name || item.title || 'Untitled';
  }
}

export default function CommandPalette({ onClose }) {
  const navigate = useNavigate();
  const { notes, projects, areas, people, tasks, openCapture } = useStore();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);
  const shortcutHint = useMemo(() => paletteShortcutLabel(), []);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const commands = useMemo(() => ([
    {
      id: 'capture-entity',
      label: 'Capture entity',
      subtitle: 'Open the quick capture modal',
      keywords: ['capture', 'new', 'create', 'quick'],
      icon: Plus,
      action: () => openCapture(),
    },
    {
      id: 'view-tasks',
      label: 'View tasks',
      subtitle: 'Jump to task board',
      keywords: ['tasks', 'todo', 'work'],
      icon: CheckSquare,
      action: () => navigate('/tasks'),
    },
    {
      id: 'view-graph',
      label: 'View graph',
      subtitle: 'Open the relationship graph',
      keywords: ['graph', 'links', 'connections'],
      icon: Network,
      action: () => navigate('/graph'),
    },
    {
      id: 'weekly-review',
      label: 'Weekly review',
      subtitle: 'Open the review view',
      keywords: ['review', 'weekly'],
      icon: Calendar,
      action: () => navigate('/review'),
    },
  ]), [navigate, openCapture]);

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
      const commandResults = commands
        .filter((command) =>
          command.label.toLowerCase().includes(q)
          || command.subtitle.toLowerCase().includes(q)
          || command.keywords.some((keyword) => keyword.includes(q))
        )
        .map((command) => ({ type: 'command', item: command }));
      const localResults = [
        ...commandResults,
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
  }, [query, notes, projects, areas, people, tasks, commands]);

  const handleSelect = useCallback((result) => {
    if (!result) return;
    const { type, item } = result;
    switch (type) {
      case 'command':
        item.action();
        break;
      case 'note':    navigate(`/notes/${item.id}`); break;
      case 'project': navigate(`/projects/${item.id}`); break;
      case 'area':    navigate(`/areas/${item.id}`); break;
      case 'person':  navigate(`/people/${item.id}`); break;
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

  const quickGroups = !query && [
    {
      label: 'Actions',
      icon: Zap,
      items: [
        { label: 'Capture entity', action: () => openCapture(), icon: Plus },
        { label: 'New project', action: () => navigate('/projects'), icon: Plus },
      ],
    },
    {
      label: 'Go to',
      icon: LayoutDashboard,
      items: [
        { label: 'View tasks', action: () => navigate('/tasks'), icon: CheckSquare },
        { label: 'View graph', action: () => navigate('/graph'), icon: Network },
        { label: 'Weekly review', action: () => navigate('/review'), icon: Calendar },
      ],
    },
  ];

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.palette} onClick={e => e.stopPropagation()}>
        <div className={styles.inputRow}>
          <Search size={16} className={styles.searchIcon} />
          <input
            ref={inputRef}
            className={styles.input}
            placeholder="Search notes, projects, people… or pick a quick action"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
          />
          {loading && <div className="spinner" />}
          {query && !loading && (
            <button type="button" onClick={() => setQuery('')} className={styles.clearBtn}>
              <X size={14} />
            </button>
          )}
          <kbd className={styles.inputHint} title={`Toggle palette (${shortcutHint})`}>{shortcutHint}</kbd>
        </div>

        {query && (
          <div className={styles.results}>
            {results.length === 0 && !loading && (
              <div className={styles.empty}>No results for &quot;{query}&quot;</div>
            )}
            {results.map((r, i) => {
              const Icon = r.type === 'command' ? (r.item.icon || Plus) : (ICON_MAP[r.type] || FileText);
              const title = getTitle(r.type, r.item);
              const subtitle = getSubtitle(r.type, r.item);
              return (
                <button
                  key={`${r.type}-${r.item.id || r.item.id || r.item.label}`}
                  type="button"
                  className={`${styles.result} ${i === activeIndex ? styles.resultActive : ''}`}
                  onClick={() => handleSelect(r)}
                  onMouseEnter={() => setActiveIndex(i)}
                >
                  <Icon size={14} className={styles.resultIcon} />
                  <div className={styles.resultContent}>
                    <span className={styles.resultTitle}>
                      {highlightMatch(title, query)}
                    </span>
                    {subtitle && (
                      <span className={styles.resultSubtitle}>
                        {highlightMatch(subtitle, query)}
                      </span>
                    )}
                  </div>
                  <ArrowRight size={12} className={styles.resultArrow} />
                </button>
              );
            })}
          </div>
        )}

        {!query && quickGroups && (
          <div className={styles.quickWrap}>
            {quickGroups.map((group) => {
              const SectionIcon = group.icon;
              return (
                <div key={group.label} className={styles.quickGroup}>
                  <div className={styles.quickGroupHeader}>
                    <SectionIcon size={14} className={styles.quickGroupIcon} aria-hidden />
                    <span>{group.label}</span>
                  </div>
                  {group.items.map((a) => {
                    const ItemIcon = a.icon;
                    return (
                      <button
                        key={a.label}
                        type="button"
                        className={styles.result}
                        onClick={() => { a.action(); onClose(); }}
                      >
                        <ItemIcon size={14} className={styles.resultIcon} />
                        <span className={styles.resultTitle}>{a.label}</span>
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        )}

        <div className={styles.footer}>
          <span><kbd>↑↓</kbd> navigate</span>
          <span>·</span>
          <span><kbd>↵</kbd> select</span>
          <span>·</span>
          <span><kbd>esc</kbd> close</span>
          <span className={styles.footerHint}><kbd>{shortcutHint}</kbd> toggle</span>
        </div>
      </div>
    </div>
  );
}
