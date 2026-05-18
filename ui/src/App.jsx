import { NavLink, Navigate, Route, Routes, useParams } from 'react-router-dom';
import styles from './App.module.css';
import V4Inbox from './views/V4Inbox';

const navItems = [
  ['/', 'Inbox'],
  ['/today', 'Today'],
  ['/search', 'Search'],
  ['/notes', 'Notes'],
  ['/projects', 'Projects'],
  ['/tasks', 'Tasks'],
  ['/areas', 'Areas'],
  ['/people', 'People'],
  ['/resources', 'Resources'],
  ['/suggestions', 'Suggestions'],
];

const routeMeta = {
  inbox: ['Inbox', 'Capture-first workspace shell. Full capture UI arrives in Cycle 11.'],
  today: ['Today', 'Execution cockpit shell. Backend and UI implementation arrives in Cycle 14.'],
  search: ['Search', 'Hybrid search shell. Full search UI arrives in Cycle 13.'],
  notes: ['Notes', 'Note list shell backed by v4 entity APIs in later cycles.'],
  projects: ['Projects', 'Project list shell backed by v4 entity APIs in later cycles.'],
  tasks: ['Tasks', 'Task list shell backed by v4 entity APIs in later cycles.'],
  areas: ['Areas', 'Area list shell backed by v4 entity APIs in later cycles.'],
  people: ['People', 'People list shell backed by v4 entity APIs in later cycles.'],
  resources: ['Resources', 'Resource list shell backed by v4 entity APIs in later cycles.'],
  suggestions: ['Suggestions', 'AI suggestion review shell backed by v4 review APIs in later cycles.'],
};

function ShellPage({ page }) {
  const [title, description] = routeMeta[page];
  return (
    <main className={styles.page}>
      <p className={styles.eyebrow}>Engram v4</p>
      <h1>{title}</h1>
      <p>{description}</p>
    </main>
  );
}

function EntityShell({ type }) {
  const { id } = useParams();
  const title = type ? `${type[0].toUpperCase()}${type.slice(1)} detail` : 'Entity detail';
  return (
    <main className={styles.page}>
      <p className={styles.eyebrow}>Engram v4</p>
      <h1>{title}</h1>
      <p>Detail route shell for entity {id}. Relationship-aware screens arrive in Cycle 12.</p>
    </main>
  );
}

export default function App() {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span>Engram</span>
          <strong>v4</strong>
        </div>
        <nav className={styles.nav}>
          {navItems.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
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
        <Route path="/today" element={<ShellPage page="today" />} />
        <Route path="/search" element={<ShellPage page="search" />} />
        <Route path="/entities/:id" element={<EntityShell />} />
        <Route path="/notes" element={<ShellPage page="notes" />} />
        <Route path="/notes/:id" element={<EntityShell type="note" />} />
        <Route path="/projects" element={<ShellPage page="projects" />} />
        <Route path="/projects/:id" element={<EntityShell type="project" />} />
        <Route path="/tasks" element={<ShellPage page="tasks" />} />
        <Route path="/tasks/:id" element={<EntityShell type="task" />} />
        <Route path="/areas" element={<ShellPage page="areas" />} />
        <Route path="/areas/:id" element={<EntityShell type="area" />} />
        <Route path="/people" element={<ShellPage page="people" />} />
        <Route path="/people/:id" element={<EntityShell type="person" />} />
        <Route path="/resources" element={<ShellPage page="resources" />} />
        <Route path="/resources/:id" element={<EntityShell type="resource" />} />
        <Route path="/suggestions" element={<ShellPage page="suggestions" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
