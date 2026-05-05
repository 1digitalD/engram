import React, { useState, useEffect, useCallback } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Inbox, FileText, FolderOpen,
  Map, Users, CheckSquare, Network, Calendar,
  Search, Plus, ChevronLeft, ChevronRight, Menu, X
} from 'lucide-react';
import styles from './AppShell.module.css';
import CommandPalette from '../search/CommandPalette';
import NoteEditor from '../notes/NoteEditor';
import useStore from '../../stores/useStore';

const NAV_ITEMS = [
  { to: '/',         icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/inbox',    icon: Inbox,           label: 'Inbox' },
  { to: '/notes',    icon: FileText,         label: 'Notes' },
  { to: '/projects', icon: FolderOpen,        label: 'Projects' },
  { to: '/areas',    icon: Map,              label: 'Areas' },
  { to: '/people',   icon: Users,            label: 'People' },
  { to: '/tasks',    icon: CheckSquare,      label: 'Tasks' },
  { to: '/graph',    icon: Network,          label: 'Graph' },
  { to: '/review',   icon: Calendar,         label: 'Review' },
];

export default function AppShell({ children }) {
  const { projects, notes } = useStore();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [collapsed, setCollapsed] = useState(false);
  const [showPalette, setShowPalette] = useState(false);
  const [showNoteEditor, setShowNoteEditor] = useState(false);

  // Keyboard shortcut for command palette
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowPalette(p => !p);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault();
        setShowNoteEditor(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const activeProjects = projects.filter(p => !p.is_archived).slice(0, 8);
  const inboxCount = notes.filter(n => n.bucket === 'INBOX').length;

  return (
    <div className={styles.shell}>
      {/* Sidebar */}
      <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
        {/* Logo */}
        <div className={styles.logo}>
          <NavLink to="/" className={styles.brand}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="9" stroke="var(--accent)" strokeWidth="1.5"/>
              <circle cx="7" cy="8" r="2" fill="var(--accent)" opacity="0.6"/>
              <circle cx="13" cy="8" r="2" fill="var(--accent)" opacity="0.6"/>
              <circle cx="10" cy="13" r="2" fill="var(--accent)"/>
              <line x1="7" y1="8" x2="10" y2="13" stroke="var(--accent)" strokeWidth="1" opacity="0.4"/>
              <line x1="13" y1="8" x2="10" y2="13" stroke="var(--accent)" strokeWidth="1" opacity="0.4"/>
            </svg>
            {!collapsed && <span className={styles.brandName}>Engram</span>}
          </NavLink>
          <button
            className={styles.collapseBtn}
            onClick={() => setCollapsed(c => !c)}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </div>

        {/* Quick capture */}
        <button
          className={styles.captureBtn}
          onClick={() => setShowNoteEditor(true)}
          title="New note (⌘N)"
        >
          <Plus size={14} />
          {!collapsed && <span>Capture</span>}
        </button>

        {/* Nav */}
        <nav className={styles.nav}>
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `${styles.navItem} ${isActive ? styles.navActive : ''}`
              }
              title={collapsed ? label : undefined}
            >
              <Icon size={16} />
              {!collapsed && <span>{label}</span>}
              {!collapsed && label === 'Inbox' && inboxCount > 0 && (
                <span className={styles.badge}>{inboxCount}</span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Projects list */}
        {!collapsed && activeProjects.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionHeader}>Projects</div>
            {activeProjects.map(p => (
              <NavLink
                key={p.id}
                to={`/projects/${p.id}`}
                className={styles.projectItem}
              >
                <span className={styles.projectDot} style={{ background: p.color || 'var(--accent)' }} />
                <span className={styles.projectName}>{p.name}</span>
              </NavLink>
            ))}
          </div>
        )}

        {/* Search */}
        <button
          className={styles.searchTrigger}
          onClick={() => setShowPalette(true)}
        >
          <Search size={13} />
          {!collapsed && <span>Search...</span>}
          {!collapsed && <kbd className={styles.kbd}>⌘K</kbd>}
        </button>
      </aside>

      {/* Main */}
      <main className={styles.main}>
        {children}
      </main>

      {/* Modals */}
      {showPalette && (
        <CommandPalette onClose={() => setShowPalette(false)} />
      )}
      {showNoteEditor && (
        <NoteEditor
          onClose={() => setShowNoteEditor(false)}
          onSaved={() => setShowNoteEditor(false)}
        />
      )}
    </div>
  );
}
