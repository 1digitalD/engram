import React, { useState, useEffect, useMemo } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Inbox, FileText, FolderOpen,
  Map, Users, CheckSquare, Network, Calendar, Sun,
  Search, Plus, ChevronLeft, ChevronRight, Menu,
} from 'lucide-react';
import styles from './AppShell.module.css';
import CommandPalette from '../search/CommandPalette';
import NoteEditor from '../notes/NoteEditor';
import useStore from '../../stores/useStore';

const NAV_ITEMS = [
  { to: '/',         icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/today',    icon: Sun,             label: 'Today' },
  { to: '/inbox',    icon: Inbox,           label: 'Inbox' },
  { to: '/notes',    icon: FileText,        label: 'Notes' },
  { to: '/projects', icon: FolderOpen,      label: 'Projects' },
  { to: '/areas',    icon: Map,             label: 'Areas' },
  { to: '/people',   icon: Users,           label: 'People' },
  { to: '/tasks',    icon: CheckSquare,     label: 'Tasks' },
  { to: '/graph',    icon: Network,         label: 'Graph' },
  { to: '/review',   icon: Calendar,        label: 'Review' },
];

const BOTTOM_NAV = [
  { to: '/today', icon: Sun,         label: 'Today' },
  { to: '/inbox', icon: Inbox,       label: 'Inbox' },
  { to: '/notes', icon: FileText,    label: 'Notes' },
  { to: '/tasks', icon: CheckSquare, label: 'Tasks' },
];

function useIsMobile() {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const q = window.matchMedia('(max-width: 768px)');
    const apply = () => setMobile(q.matches);
    apply();
    q.addEventListener('change', apply);
    return () => q.removeEventListener('change', apply);
  }, []);
  return mobile;
}

function paletteKbdHint() {
  if (typeof navigator === 'undefined') return '⌘K';
  return /Mac|iPhone|iPad|iPod/i.test(navigator.userAgent) ? '⌘K' : 'Ctrl+K';
}

export default function AppShell({ children }) {
  const { projects, notes, captureOpen, closeCapture } = useStore();
  const location = useLocation();
  const isMobile = useIsMobile();

  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showPalette, setShowPalette] = useState(false);
  const [showNoteEditor, setShowNoteEditor] = useState(false);

  const kbdPalette = useMemo(() => paletteKbdHint(), []);

  const sidebarCollapsed = isMobile ? false : collapsed;

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (captureOpen) {
      setShowNoteEditor(true);
      closeCapture();
    }
  }, [captureOpen, closeCapture]);

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowPalette((p) => !p);
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

  const closeDrawer = () => setDrawerOpen(false);
  const navEndProps = isMobile ? { onClick: closeDrawer } : {};

  return (
    <div className={`${styles.shell} ${drawerOpen ? styles.drawerOpen : ''}`}>
      <header className={styles.topBar}>
        <div className={styles.topLeft}>
          {isMobile && (
            <button
              type="button"
              className={styles.iconBtn}
              aria-label="Open menu"
              onClick={() => setDrawerOpen(true)}
            >
              <Menu size={18} />
            </button>
          )}
          <NavLink
            to="/today"
            className={({ isActive }) =>
              `${styles.todayBtn} ${isActive ? styles.todayBtnActive : ''}`
            }
            title="Today"
          >
            <Sun size={20} strokeWidth={2.25} />
          </NavLink>
          <NavLink to="/" className={styles.topBrand} end>
            Engram
          </NavLink>
        </div>
        <div className={styles.topRight}>
          <button
            type="button"
            className={styles.topSearch}
            onClick={() => setShowPalette(true)}
          >
            <Search size={15} />
            <span className={styles.topSearchLabel}>Search or run command…</span>
            <kbd className={styles.kbd}>{kbdPalette}</kbd>
          </button>
        </div>
      </header>

      <div className={styles.body}>
        {isMobile && drawerOpen && (
          <button
            type="button"
            className={styles.scrim}
            aria-label="Close menu"
            onClick={closeDrawer}
          />
        )}

        <aside
          className={`${styles.sidebar} ${sidebarCollapsed ? styles.collapsed : ''} ${
            isMobile ? styles.sidebarDrawer : ''
          }`}
        >
          <div className={styles.logo}>
            <NavLink to="/" className={styles.brand} onClick={closeDrawer} end>
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <circle cx="10" cy="10" r="9" stroke="var(--accent)" strokeWidth="1.5"/>
                <circle cx="7" cy="8" r="2" fill="var(--accent)" opacity="0.6"/>
                <circle cx="13" cy="8" r="2" fill="var(--accent)" opacity="0.6"/>
                <circle cx="10" cy="13" r="2" fill="var(--accent)"/>
                <line x1="7" y1="8" x2="10" y2="13" stroke="var(--accent)" strokeWidth="1" opacity="0.4"/>
                <line x1="13" y1="8" x2="10" y2="13" stroke="var(--accent)" strokeWidth="1" opacity="0.4"/>
              </svg>
              {!sidebarCollapsed && <span className={styles.brandName}>Engram</span>}
            </NavLink>
            {!isMobile && (
              <button
                className={styles.collapseBtn}
                onClick={() => setCollapsed(c => !c)}
                title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
              </button>
            )}
            {isMobile && (
              <button
                className={styles.collapseBtn}
                onClick={closeDrawer}
                title="Close"
                aria-label="Close menu"
              >
                <ChevronLeft size={14} />
              </button>
            )}
          </div>

          <button
            className={styles.captureBtn}
            onClick={() => {
              setShowNoteEditor(true);
              closeDrawer();
            }}
            title="New note (⌘N)"
          >
            <Plus size={14} />
            {!sidebarCollapsed && <span>Capture</span>}
          </button>

          <nav className={styles.nav}>
            {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `${styles.navItem} ${isActive ? styles.navActive : ''}`
                }
                title={sidebarCollapsed ? label : undefined}
                {...navEndProps}
              >
                <Icon size={16} />
                {!sidebarCollapsed && <span>{label}</span>}
                {!sidebarCollapsed && label === 'Inbox' && inboxCount > 0 && (
                  <span className={styles.badge}>{inboxCount}</span>
                )}
              </NavLink>
            ))}
          </nav>

          {!sidebarCollapsed && activeProjects.length > 0 && (
            <div className={styles.section}>
              <div className={styles.sectionHeader}>Projects</div>
              {activeProjects.map(p => (
                <NavLink
                  key={p.id}
                  to={`/projects/${p.id}`}
                  className={styles.projectItem}
                  onClick={closeDrawer}
                >
                  <span className={styles.projectDot} style={{ background: p.color || 'var(--accent)' }} />
                  <span className={styles.projectName}>{p.name}</span>
                </NavLink>
              ))}
            </div>
          )}

          <button
            className={styles.searchTrigger}
            onClick={() => {
              setShowPalette(true);
              closeDrawer();
            }}
          >
            <Search size={13} />
            {!sidebarCollapsed && <span>Command palette…</span>}
            {!sidebarCollapsed && <kbd className={styles.kbd}>{kbdPalette}</kbd>}
          </button>
        </aside>

        <main className={styles.main}>{children}</main>
      </div>

      {isMobile && (
        <nav className={styles.bottomNav} aria-label="Primary">
          {BOTTOM_NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `${styles.bottomNavItem} ${isActive ? styles.bottomNavActive : ''}`
              }
            >
              <Icon size={20} />
              <span>{label}</span>
            </NavLink>
          ))}
          <button
            type="button"
            className={styles.bottomNavItem}
            onClick={() => setDrawerOpen(true)}
          >
            <Menu size={20} />
            <span>More</span>
          </button>
        </nav>
      )}

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
