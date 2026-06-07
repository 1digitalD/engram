import { useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import {
  Check,
  CheckSquare2,
  FilePlus2,
  House,
  Inbox,
  Plus,
  Sun,
  Search,
  Sparkles,
  FileText,
  FolderKanban,
  CheckSquare,
  Layers,
  Users,
  Link2,
} from 'lucide-react';
import styles from './App.module.css';
import { v4API } from './api/v4Client';
import MarkdownEditor from './components/MarkdownEditor';
import { getTodayAttentionCount } from './utils/today';
import V4Inbox from './views/V4Inbox';
import V4EntityList from './views/V4EntityList';
import V4EntityDetail from './views/V4EntityDetail';
import V4Home from './views/V4Home';
import V4Search from './views/V4Search';
import V4Today from './views/V4Today';
import V4Suggestions from './views/V4Suggestions';

const viewItems = [
  ['/', 'Home', House, null],
  ['/inbox', 'Inbox', Inbox, 'inbox'],
  ['/today', 'Today', Sun, 'today'],
  ['/search', 'Search', Search, null],
  ['/suggestions', 'Suggestions', Sparkles, 'suggestions'],
];

const libraryItems = [
  ['/notes', 'Notes', FileText],
  ['/projects', 'Projects', FolderKanban],
  ['/tasks', 'Tasks', CheckSquare],
  ['/areas', 'Areas', Layers],
  ['/people', 'People', Users],
  ['/resources', 'Resources', Link2],
];

function useSidebarCounts(refreshKey) {
  const [counts, setCounts] = useState({ inbox: null, today: null, suggestions: null });

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      v4API.inbox({ limit: 200 }),
      v4API.today(),
      v4API.suggestions.list({ status: 'pending', limit: 1 }),
    ]).then(([inboxRes, todayRes, sugRes]) => {
      if (!active) return;
      const inboxCount = inboxRes.status === 'fulfilled'
        ? (inboxRes.value.needs_review?.length ?? null)
        : null;
      const todayCount = todayRes.status === 'fulfilled'
        ? getTodayAttentionCount(todayRes.value)
        : null;
      const sugCount = sugRes.status === 'fulfilled'
        ? (sugRes.value.meta?.total ?? sugRes.value.data?.length ?? null)
        : null;
      setCounts({ inbox: inboxCount, today: todayCount, suggestions: sugCount });
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
                <MarkdownEditor
                  value={noteContent}
                  onChange={setNoteContent}
                  placeholder="Capture a note from anywhere…"
                  minRows={3}
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

export default function App() {
  const location = useLocation();
  const counts = useSidebarCounts(location.pathname + location.search);
  const showQuickActions = location.pathname === '/';
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span>Engram</span>
          <strong>v4</strong>
        </div>
        <nav className={styles.nav}>
          <p className={styles.navSection}>Views</p>
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
          <p className={styles.navSection}>Library</p>
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
        </nav>
      </aside>
      <div className={styles.mainColumn}>
        {showQuickActions ? <QuickActionBar /> : null}
        <div className={styles.routeViewport}>
          <Routes>
            <Route path="/" element={<V4Home />} />
            <Route path="/inbox" element={<V4Inbox />} />
            <Route path="/today" element={<V4Today />} />
            <Route path="/search" element={<V4Search />} />
            <Route path="/entities/:id" element={<V4EntityDetail />} />
            <Route path="/notes" element={<V4EntityList type="note" />} />
            <Route path="/notes/:id" element={<V4EntityDetail type="note" />} />
            <Route path="/projects" element={<V4EntityList type="project" />} />
            <Route path="/projects/:id" element={<V4EntityDetail type="project" />} />
            <Route path="/tasks" element={<V4EntityList type="task" />} />
            <Route path="/tasks/:id" element={<V4EntityDetail type="task" />} />
            <Route path="/areas" element={<V4EntityList type="area" />} />
            <Route path="/areas/:id" element={<V4EntityDetail type="area" />} />
            <Route path="/people" element={<V4EntityList type="person" />} />
            <Route path="/people/:id" element={<V4EntityDetail type="person" />} />
            <Route path="/resources" element={<V4EntityList type="resource" />} />
            <Route path="/resources/:id" element={<V4EntityDetail type="resource" />} />
            <Route path="/suggestions" element={<V4Suggestions />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
