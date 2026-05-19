import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import styles from './App.module.css';
import V4Inbox from './views/V4Inbox';
import V4EntityList from './views/V4EntityList';
import V4EntityDetail from './views/V4EntityDetail';
import V4Search from './views/V4Search';
import V4Today from './views/V4Today';
import V4Suggestions from './views/V4Suggestions';

const viewItems = [
  ['/', 'Inbox'],
  ['/today', 'Today'],
  ['/search', 'Search'],
  ['/suggestions', 'Suggestions'],
];

const libraryItems = [
  ['/notes', 'Notes'],
  ['/projects', 'Projects'],
  ['/tasks', 'Tasks'],
  ['/areas', 'Areas'],
  ['/people', 'People'],
  ['/resources', 'Resources'],
];

export default function App() {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span>Engram</span>
          <strong>v4</strong>
        </div>
        <nav className={styles.nav}>
          <p className={styles.navSection}>Views</p>
          {viewItems.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}
            >
              {label}
            </NavLink>
          ))}
          <p className={styles.navSection}>Library</p>
          {libraryItems.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}
            >
              {label}
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
