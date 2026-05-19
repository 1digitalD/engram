import { useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import {
  Inbox,
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
import V4Inbox from './views/V4Inbox';
import V4EntityList from './views/V4EntityList';
import V4EntityDetail from './views/V4EntityDetail';
import V4Search from './views/V4Search';
import V4Today from './views/V4Today';
import V4Suggestions from './views/V4Suggestions';

const viewItems = [
  ['/', 'Inbox', Inbox, 'inbox'],
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

function useSidebarCounts() {
  const [counts, setCounts] = useState({ inbox: null, today: null, suggestions: null });

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      v4API.entities.list({ type: 'note', status: 'active', limit: 1 }),
      v4API.today(),
      v4API.suggestions.list({ status: 'pending', limit: 1 }),
    ]).then(([inboxRes, todayRes, sugRes]) => {
      if (!active) return;
      const inboxCount = inboxRes.status === 'fulfilled'
        ? (inboxRes.value.meta?.total ?? inboxRes.value.data?.length ?? null)
        : null;
      const todayCount = todayRes.status === 'fulfilled'
        ? ((todayRes.value.follow_ups?.length || 0)
          + (todayRes.value.blocked_or_waiting_tasks?.length || 0))
        : null;
      const sugCount = sugRes.status === 'fulfilled'
        ? (sugRes.value.meta?.total ?? sugRes.value.data?.length ?? null)
        : null;
      setCounts({ inbox: inboxCount, today: todayCount, suggestions: sugCount });
    });
    return () => { active = false; };
  }, []);

  return counts;
}

export default function App() {
  const counts = useSidebarCounts();
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

      <Routes>
        <Route path="/" element={<V4Inbox />} />
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
  );
}
