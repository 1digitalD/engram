import { useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import {
  Check,
  CheckSquare2,
  FilePlus2,
  House,
  Inbox,
  Moon,
  Plus,
  Snowflake,
  Sparkles,
  Sun,
  Search,
  FileText,
  FolderKanban,
  CheckSquare,
  Layers,
  Users,
  Link2,
  GitBranch,
} from 'lucide-react';
import styles from './App.module.css';
import { v4API } from './api/v4Client';
import V4Inbox from './views/V4Inbox';
import V4EntityList from './views/V4EntityList';
import V5ThreadDetail from './views/V5ThreadDetail';
import V4Home from './views/V4Home';
import V4Search from './views/V4Search';
import V4Today from './views/V4Today';
import V4Suggestions from './views/V4Suggestions';
import V4AgentActivity from './views/V4AgentActivity';
import V5Threads from './views/V5Threads';
import V5Now from './views/V5Now';
import TopBar from './components/TopBar';
import { CaptureProvider, useCapture } from './context/CaptureContext';
import V5CaptureSheet, { CaptureFab, CaptureToast } from './views/V5CaptureSheet';

const viewItems = [
  ['/', 'Home', House, null],
  ['/inbox', 'Inbox', Inbox, 'inbox'],
  ['/today', 'Today', Sun, 'today'],
  ['/threads', 'Threads', GitBranch, null],
  ['/search', 'Search', Search, null],
];

const libraryItems = [
  ['/notes', 'Notes', FileText],
  ['/projects', 'Projects', FolderKanban],
  ['/tasks', 'Tasks', CheckSquare],
  ['/areas', 'Areas', Layers],
  ['/people', 'People', Users],
  ['/resources', 'Resources', Link2],
];

const themeOptions = [
  ['light', 'Light', Sun],
  ['dark', 'Dark', Moon],
  ['glass', 'Glass', Sparkles],
  ['frost', 'Frost', Snowflake],
];

function getInitialTheme() {
  try {
    const saved = localStorage.getItem('engram-theme');
    if (themeOptions.some(([value]) => value === saved)) return saved;
  } catch { /* localStorage unavailable */ }
  if (typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
}

function isV5Enabled() {
  if (typeof window === 'undefined') return false;
  try {
    const saved = localStorage.getItem('engram-v5-enabled');
    if (saved === 'true') return true;
    if (saved === 'false') return false;
  } catch { /* localStorage unavailable */ }
  return import.meta.env?.VITE_ENGRAM_V5 === 'true';
}

function V5RecallPlaceholder() {
  return (
    <main className={styles.today}>
      <section className={styles.panel}>
        <h2>Recall</h2>
        <p>Recall lens is coming in a future slice.</p>
      </section>
    </main>
  );
}

function ThemeSwitcher() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // Persist only on explicit choice so OS-preference users keep following
  // prefers-color-scheme until they pick a theme themselves.
  function chooseTheme(value) {
    setTheme(value);
    try {
      localStorage.setItem('engram-theme', value);
    } catch { /* localStorage unavailable */ }
  }

  return (
    <div className={styles.themeSwitcher} role="group" aria-label="Theme">
      {themeOptions.map(([value, label, Icon]) => (
        <button
          key={value}
          type="button"
          aria-pressed={theme === value}
          title={`${label} theme`}
          aria-label={`${label} theme`}
          className={`${styles.themeOption} ${theme === value ? styles.themeOptionActive : ''}`}
          onClick={() => chooseTheme(value)}
        >
          <Icon size={14} strokeWidth={2} aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}

function useSidebarCounts(refreshKey) {
  const [counts, setCounts] = useState({ inbox: null, today: null });

  useEffect(() => {
    let active = true;
    v4API.summary().then((data) => {
      if (!active) return;
      setCounts({
        inbox: data?.inbox_count ?? null,
        today: data?.today_count ?? null,
      });
    }).catch(() => {
      if (!active) return;
      setCounts({ inbox: null, today: null });
    });
    return () => { active = false; };
  }, [refreshKey]);

  return counts;
}

function QuickActionBar() {
  const navigate = useNavigate();
  const [mode, setMode] = useState('');
  const [noteContent, setNoteContent] = useState('');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const isNote = mode === 'note';
  const isTask = mode === 'task';
  const isProject = mode === 'project';

  function resetForm(nextMode = '') {
    setMode(nextMode);
    setNoteContent('');
    setTitle('');
    setContent('');
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setMessage('');
    try {
      if (isNote) {
        const trimmed = noteContent.trim();
        if (!trimmed) return;
        await v4API.capture({
          content: trimmed,
          source: 'ui',
          mode: 'auto',
        });
        resetForm('');
        setMessage('Saved note');
      } else if (isTask || isProject) {
        const trimmedTitle = title.trim();
        if (!trimmedTitle) return;
        await v4API.entities.create({
          type: isTask ? 'task' : 'project',
          title: trimmedTitle,
          content: content.trim() || null,
        });
        resetForm('');
        setMessage(isTask ? 'Created task' : 'Created project');
      }
    } catch (err) {
      setMessage(err.message || 'Action failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.quickBar}>
      <div className={styles.quickBarHeader}>
        <div className={styles.quickBarActions}>
          <button
            type="button"
            className={`${styles.quickChip} ${isNote ? styles.quickChipActive : ''}`}
            onClick={() => resetForm(isNote ? '' : 'note')}
          >
            <FilePlus2 size={14} strokeWidth={2.2} aria-hidden="true" />
            Note
          </button>
          <button
            type="button"
            className={`${styles.quickChip} ${isTask ? styles.quickChipActive : ''}`}
            onClick={() => resetForm(isTask ? '' : 'task')}
          >
            <CheckSquare2 size={14} strokeWidth={2.2} aria-hidden="true" />
            Task
          </button>
          <button
            type="button"
            className={`${styles.quickChip} ${isProject ? styles.quickChipActive : ''}`}
            onClick={() => resetForm(isProject ? '' : 'project')}
          >
            <Plus size={14} strokeWidth={2.2} aria-hidden="true" />
            Project
          </button>
          <button
            type="button"
            className={styles.quickChip}
            onClick={() => navigate('/search')}
          >
            <Search size={14} strokeWidth={2.2} aria-hidden="true" />
            Search
          </button>
        </div>
        {message ? (
          <span className={styles.quickMessage} role="status" aria-live="polite">
            <Check size={13} strokeWidth={2.4} aria-hidden="true" />
            {message}
          </span>
        ) : null}
      </div>

      {mode ? (
        <form onSubmit={handleSubmit} className={styles.quickForm}>
          {isNote ? (
            <>
              <div className={styles.quickEditorWrap}>
                <textarea
                  value={noteContent}
                  onChange={(event) => setNoteContent(event.target.value)}
                  placeholder="Capture a note from anywhere…"
                  aria-label="Quick note content"
                  rows={3}
                />
              </div>
              <button
                type="submit"
                className={styles.quickSubmit}
                disabled={!noteContent.trim() || busy}
              >
                {busy ? 'Saving…' : 'Save note'}
              </button>
            </>
          ) : (
            <>
              <div className={styles.quickFields}>
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder={isTask ? 'New task title' : 'New project title'}
                  aria-label={isTask ? 'Quick task title' : 'Quick project title'}
                />
                <textarea
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  placeholder="Optional context"
                  aria-label={isTask ? 'Quick task content' : 'Quick project content'}
                  rows={2}
                />
              </div>
              <button
                type="submit"
                className={styles.quickSubmit}
                disabled={!title.trim() || busy}
              >
                {busy ? 'Saving…' : (isTask ? 'Create task' : 'Create project')}
              </button>
            </>
          )}
        </form>
      ) : null}
    </section>
  );
}

function V4AppShell() {
  const location = useLocation();
  const counts = useSidebarCounts(location.pathname + location.search);
  const showQuickActions = location.pathname === '/';
  const { toast } = useCapture();
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span>Engram</span>
          <strong>v4</strong>
        </div>
        <nav className={styles.nav}>
          <div className={styles.navGroup}>
            <p className={styles.navSection}>Views</p>
            <div className={styles.navGroupLinks}>
              {viewItems.map(([to, label, Icon, countKey]) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}
                >
                  <Icon size={16} strokeWidth={2} aria-hidden="true" />
                  <span className={styles.navLabel}>{label}</span>
                  {countKey && counts[countKey] ? (
                    <span className={styles.navCount}>{counts[countKey]}</span>
                  ) : null}
                </NavLink>
              ))}
            </div>
          </div>
          <div className={styles.navGroup}>
            <p className={styles.navSection}>Library</p>
            <div className={styles.navGroupLinks}>
              {libraryItems.map(([to, label, Icon]) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}
                >
                  <Icon size={16} strokeWidth={2} aria-hidden="true" />
                  <span className={styles.navLabel}>{label}</span>
                </NavLink>
              ))}
            </div>
          </div>
        </nav>
        <ThemeSwitcher />
      </aside>
      <div className={styles.mainColumn}>
        {showQuickActions ? <QuickActionBar /> : null}
        <div className={styles.routeViewport}>
          <Routes>
            <Route path="/" element={<V4Home />} />
            <Route path="/inbox" element={<V4Inbox />} />
            <Route path="/today" element={<V4Today />} />
            <Route path="/threads" element={<V5Threads />} />
            <Route path="/search" element={<V4Search />} />
            <Route path="/agent-activity" element={<V4AgentActivity />} />
            <Route path="/entities/:id" element={<V5ThreadDetail />} />
            <Route path="/notes" element={<V4EntityList type="note" />} />
            <Route path="/notes/:id" element={<V5ThreadDetail type="note" />} />
            <Route path="/projects" element={<V4EntityList type="project" />} />
            <Route path="/projects/:id" element={<V5ThreadDetail type="project" />} />
            <Route path="/tasks" element={<V4EntityList type="task" />} />
            <Route path="/tasks/:id" element={<V5ThreadDetail type="task" />} />
            <Route path="/areas" element={<V4EntityList type="area" />} />
            <Route path="/areas/:id" element={<V5ThreadDetail type="area" />} />
            <Route path="/people" element={<V4EntityList type="person" />} />
            <Route path="/people/:id" element={<V5ThreadDetail type="person" />} />
            <Route path="/resources" element={<V4EntityList type="resource" />} />
            <Route path="/resources/:id" element={<V5ThreadDetail type="resource" />} />
            <Route path="/suggestions" element={<V4Suggestions />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
      <CaptureFab />
      <V5CaptureSheet />
      <CaptureToast toast={toast} />
    </div>
  );
}

function V5AppShell() {
  const location = useLocation();
  const { toast, openCapture } = useCapture();
  const [counts, setCounts] = useState({ today: 0, threads: 0, recall: 0 });

  useEffect(() => {
    let active = true;
    v4API.summary()
      .then((data) => {
        if (!active) return;
        setCounts({
          today: data?.today_count ?? 0,
          threads: data?.threads_count ?? data?.today_count ?? 0,
          recall: data?.recall_count ?? 0,
        });
      })
      .catch(() => {
        if (!active) return;
        setCounts({ today: 0, threads: 0, recall: 0 });
      });
    return () => { active = false; };
  }, [location.pathname]);

  return (
    <div className={styles.shell} data-v5="true">
      <TopBar
        onAsk={openCapture}
        nowCount={counts.today}
        threadsCount={counts.threads}
        recallCount={counts.recall}
      />
      <div className={styles.mainColumn}>
        <div className={styles.routeViewport}>
          <Routes>
            <Route path="/" element={<Navigate to="/now" replace />} />
            <Route path="/now" element={<V5Now />} />
            <Route path="/threads" element={<V5Threads />} />
            <Route path="/recall" element={<V5RecallPlaceholder />} />
            <Route path="/entities/:id" element={<V5ThreadDetail />} />
            <Route path="/notes" element={<V4EntityList type="note" />} />
            <Route path="/notes/:id" element={<V5ThreadDetail type="note" />} />
            <Route path="/projects" element={<V4EntityList type="project" />} />
            <Route path="/projects/:id" element={<V5ThreadDetail type="project" />} />
            <Route path="/tasks" element={<V4EntityList type="task" />} />
            <Route path="/tasks/:id" element={<V5ThreadDetail type="task" />} />
            <Route path="/areas" element={<V4EntityList type="area" />} />
            <Route path="/areas/:id" element={<V5ThreadDetail type="area" />} />
            <Route path="/people" element={<V4EntityList type="person" />} />
            <Route path="/people/:id" element={<V5ThreadDetail type="person" />} />
            <Route path="/resources" element={<V4EntityList type="resource" />} />
            <Route path="/resources/:id" element={<V5ThreadDetail type="resource" />} />
            <Route path="*" element={<Navigate to="/now" replace />} />
          </Routes>
        </div>
      </div>
      <CaptureFab />
      <V5CaptureSheet />
      <CaptureToast toast={toast} />
    </div>
  );
}

export default function App() {
  const [v5, setV5] = useState(isV5Enabled);

  useEffect(() => {
    function handleStorage(event) {
      if (event.key === 'engram-v5-enabled') {
        setV5(event.newValue === 'true');
      }
    }
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  return (
    <CaptureProvider>
      {v5 ? <V5AppShell /> : <V4AppShell />}
    </CaptureProvider>
  );
}
