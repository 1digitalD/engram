import { useEffect, useMemo, useState } from 'react';
import {
  Navigate, NavLink, Route, Routes, useLocation,
} from 'react-router-dom';
import { ArrowLeft, Search } from 'lucide-react';
import { legacyPath } from '../legacy/legacyPaths';
import LabEntityList from './LabEntityList';
import LabEntityDetail from './LabEntityDetail';
import LabPeople from './LabPeople';
import LabSearch from './LabSearch';
import LabToday from './LabToday';
import LabCapture from './LabCapture';
import styles from './LabShell.module.css';

const navItems = [
  { to: legacyPath('/lab/today'), label: 'Today' },
  { to: legacyPath('/lab/notes'), label: 'Notes' },
  { to: legacyPath('/lab/tasks'), label: 'Tasks' },
  { to: legacyPath('/lab/projects'), label: 'Projects' },
  { to: legacyPath('/lab/areas'), label: 'Areas' },
  { to: legacyPath('/lab/people'), label: 'People' },
  { to: legacyPath('/lab/resources'), label: 'Resources' },
];

const PAGE_TITLE = {
  [legacyPath('/lab/today')]: 'Today',
  [legacyPath('/lab/notes')]: 'Notes',
  [legacyPath('/lab/tasks')]: 'Tasks',
  [legacyPath('/lab/projects')]: 'Projects',
  [legacyPath('/lab/areas')]: 'Areas',
  [legacyPath('/lab/people')]: 'People',
  [legacyPath('/lab/resources')]: 'Resources',
};

function pageTitle(pathname) {
  return PAGE_TITLE[pathname] || 'Lab';
}

export default function LabShell() {
  const location = useLocation();
  const [searchOpen, setSearchOpen] = useState(false);
  const [captureOpen, setCaptureOpen] = useState(false);
  const title = useMemo(() => pageTitle(location.pathname), [location.pathname]);

  useEffect(() => {
    function onKeyDown(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setSearchOpen(true);
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <div className={styles.shell} data-lab="true">
      <aside className={styles.sidebar}>
        <NavLink to={legacyPath('/now')} className={styles.brand} aria-label="Engram home">
          <span className={styles.brandGlyph} aria-hidden="true">◈</span>
          <span>Engram</span>
        </NavLink>

        <NavLink to={legacyPath('/now')} className={styles.backLink}>
          <ArrowLeft size={14} strokeWidth={2} aria-hidden="true" />
          Back to classic
        </NavLink>

        <nav className={styles.nav} aria-label="Lab navigation">
          {navItems.map(({ to, label }) => {
            const isActive = location.pathname === to
              || (to !== legacyPath('/lab/today') && location.pathname.startsWith(to));
            return (
              <NavLink
                key={to}
                to={to}
                aria-current={isActive ? 'page' : undefined}
                className={({ isActive: navActive }) => (
                  `${styles.navLink} ${navActive ? styles.navLinkActive : ''}`.trim()
                )}
              >
                {label}
              </NavLink>
            );
          })}
        </nav>

        <div className={styles.betaBadge}>LAB redesign</div>
      </aside>

      <div className={styles.main}>
        <header className={styles.topbar}>
          <h1 className={styles.topbarTitle}>{title}</h1>
          <button
            type="button"
            className={styles.searchTrigger}
            onClick={() => setCaptureOpen(true)}
            aria-label="Open capture"
          >
            Capture
          </button>
          <button
            type="button"
            className={styles.searchTrigger}
            onClick={() => setSearchOpen(true)}
            aria-label="Open search"
          >
            <Search size={14} strokeWidth={2} aria-hidden="true" />
            <span>Search</span>
            <kbd>⌘K</kbd>
          </button>
        </header>

        <main className={styles.content}>
          <Routes>
            <Route index element={<Navigate to="today" replace />} />
            <Route path="today" element={<LabToday />} />
            <Route path="notes" element={<LabEntityList type="note" onOpenCapture={() => setCaptureOpen(true)} />} />
            <Route path="notes/:id" element={<LabEntityDetail />} />
            <Route path="tasks" element={<LabEntityList type="task" onOpenCapture={() => setCaptureOpen(true)} />} />
            <Route path="tasks/:id" element={<LabEntityDetail />} />
            <Route path="projects" element={<LabEntityList type="project" onOpenCapture={() => setCaptureOpen(true)} />} />
            <Route path="projects/:id" element={<LabEntityDetail />} />
            <Route path="areas" element={<LabEntityList type="area" onOpenCapture={() => setCaptureOpen(true)} />} />
            <Route path="areas/:id" element={<LabEntityDetail />} />
            <Route path="people" element={<LabPeople />} />
            <Route path="people/:id" element={<LabEntityDetail />} />
            <Route path="resources" element={<LabEntityList type="resource" onOpenCapture={() => setCaptureOpen(true)} />} />
            <Route path="resources/:id" element={<LabEntityDetail />} />
          </Routes>
        </main>
      </div>

      <LabSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
      <LabCapture open={captureOpen} onClose={() => setCaptureOpen(false)} />
    </div>
  );
}
